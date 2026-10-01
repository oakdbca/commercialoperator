import json
import re
from django.db import transaction
from django.db.models import Q, Value
from django.db.models.functions import Concat, Coalesce
from django.db.models import QuerySet
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.conf import settings
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from commercialoperator.components.proposals.models import (
    ProposalAccreditation,
    ProposalDocument,
    ProposalFilmingActivity,
    ProposalPark,
    ProposalParkActivity,
    ProposalParkAccess,
    ProposalTrail,
    ProposalTrailSectionActivity,
    ProposalTrailSection,
    ProposalParkZone,
    ProposalParkZoneActivity,
    ProposalOtherDetails,
    ProposalUserAction,
    ProposalAssessment,
    ProposalAssessmentAnswer,
    ChecklistQuestion,
)
from commercialoperator.components.proposals.serializers_event import (
    ProposalEventOtherDetailsSerializer,
    ProposalEventManagementSerializer,
    ProposalEventActivitiesSerializer,
    ProposalEventVehiclesVesselsSerializer,
)
from commercialoperator.components.approvals.models import Approval
from commercialoperator.components.proposals.email import (
    send_submit_email_notification,
    send_external_submit_email_notification,
)
from commercialoperator.components.proposals.serializers import (
    InternalEventProposalSerializer,
    InternalFilmingProposalSerializer,
    InternalProposalSerializer,
    SaveProposalSerializer,
    ProposalAccreditationSerializer,
    ProposalOtherDetailsSerializer,
    SaveInternalFilmingProposalSerializer,
    SaveInternalEventProposalSerializer,
    ProposalInformationStandardSerializer,
    ProposalEmissionStandardSerializer,
)
from commercialoperator.components.main.models import (
    Activity,
    Park,
    AccessType,
    Trail,
    Section,
    Zone,
)
from commercialoperator.components.organisations.models import Organisation, OrganisationContact

import traceback
import os
from datetime import datetime


import logging

from commercialoperator.components.segregation.decorators import basic_exception_handler
from commercialoperator.components.segregation.utils import QuerySetChain

logger = logging.getLogger(__name__)


def create_data_from_form(
    schema,
    post_data,
    file_data,
    post_data_index=None,
    special_fields=[],
    assessor_data=False,
):
    data = {}
    special_fields_list = []
    assessor_data_list = []
    comment_data_list = {}
    special_fields_search = SpecialFieldsSearch(special_fields)
    if assessor_data:
        assessor_fields_search = AssessorDataSearch()
        comment_fields_search = CommentDataSearch()
    try:
        for item in schema:
            data.update(_create_data_from_item(item, post_data, file_data, 0, ""))
            # _create_data_from_item(item, post_data, file_data, 0, '')
            special_fields_search.extract_special_fields(
                item, post_data, file_data, 0, ""
            )
            if assessor_data:
                assessor_fields_search.extract_special_fields(
                    item, post_data, file_data, 0, ""
                )
                comment_fields_search.extract_special_fields(
                    item, post_data, file_data, 0, ""
                )
        special_fields_list = special_fields_search.special_fields
        if assessor_data:
            assessor_data_list = assessor_fields_search.assessor_data
            comment_data_list = comment_fields_search.comment_data
    except:
        traceback.print_exc()
    if assessor_data:
        return [data], special_fields_list, assessor_data_list, comment_data_list

    return [data], special_fields_list


def _extend_item_name(name, suffix, repetition):
    return "{}{}-{}".format(name, suffix, repetition)


def _create_data_from_item(item, post_data, file_data, repetition, suffix):
    item_data = {}

    if "name" in item:
        extended_item_name = item["name"]
    else:
        raise Exception("Missing name in item %s" % item["label"])

    if "children" not in item:
        if item["type"] in ["checkbox" "declaration"]:
            # item_data[item['name']] = post_data[item['name']]
            item_data[item["name"]] = extended_item_name in post_data
        elif item["type"] == "file":
            if extended_item_name in file_data:
                item_data[item["name"]] = str(file_data.get(extended_item_name))
            elif (
                extended_item_name + "-existing" in post_data
                and len(post_data[extended_item_name + "-existing"]) > 0
            ):
                item_data[item["name"]] = post_data.get(
                    extended_item_name + "-existing"
                )
            else:
                item_data[item["name"]] = ""
        else:
            if extended_item_name in post_data:
                if item["type"] == "multi-select":
                    item_data[item["name"]] = post_data.getlist(extended_item_name)
                else:
                    item_data[item["name"]] = post_data.get(extended_item_name)
    else:
        if "repetition" in item:
            item_data = generate_item_data(
                extended_item_name,
                item,
                item_data,
                post_data,
                file_data,
                len(post_data[item["name"]]),
                suffix,
            )
        else:
            item_data = generate_item_data(
                extended_item_name, item, item_data, post_data, file_data, 1, suffix
            )

    if "conditions" in item:
        for condition in item["conditions"].keys():
            for child in item["conditions"][condition]:
                item_data.update(
                    _create_data_from_item(
                        child, post_data, file_data, repetition, suffix
                    )
                )

    return item_data


def generate_item_data(
    item_name, item, item_data, post_data, file_data, repetition, suffix
):
    item_data_list = []
    for rep in range(repetition):
        child_data = {}
        for child_item in item.get("children"):
            child_data.update(
                _create_data_from_item(
                    child_item, post_data, file_data, 0, "{}-{}".format(suffix, rep)
                )
            )
        item_data_list.append(child_data)

        item_data[item["name"]] = item_data_list
    return item_data

def request_has_filters(request) -> bool:
    """
    Returns True iff the request contains any search/filter param you care about.
    Adjust the keys to match your frontend.
    """
    params = _get_params(request)

    # Global search (DataTables)
    if (params.get("search[value]") or "").strip():
        return True

    # Date range filters (support both pairs)
    if (params.get("date_from") or params.get("start_date") or "").strip():
        return True
    if (params.get("date_to") or params.get("end_date") or "").strip():
        return True

    # Processing status
    status = (params.get("datatable_filter_processing_status") or params.get("processing_status") or "").strip()
    if status and status.lower() != "all":
        return True

    # Application type (license type)
    app_type_name = (params.get("datatable_filter_application_type__name") or params.get("license_type") or "").strip()
    if app_type_name and app_type_name.lower() != "all":
        return True

    # Submitter selection
    submitter_email = (params.get("datatable_filter_submitter__email") or params.get("submitter") or "").strip()
    if submitter_email and submitter_email.lower() != "all":
        return True

    # Specific filters for organisations
    organisation = (params.get("datatable_filter_name") or "").strip()
    if organisation and organisation.lower() != "all":
        return True

    # Applicant name filter
    applicant = (params.get("datatable_filter_full_name") or "").strip()
    if applicant and applicant.lower() != "all":
        return True
    # Role filter
    role = (params.get("datatable_filter_role") or "").strip()
    if role and role.lower() != "all":
        return True
    # Status filter
    status = (params.get("datatable_filter_status") or "").strip()
    if status and status.lower() != "all":
        return True
    return False

def _get_params(request) -> dict:
    """
    Extract query params from either DRF Request or Django HttpRequest.
    Works with request.query_params or request.GET.
    """
    if hasattr(request, "query_params"):
        return request.query_params
    elif hasattr(request, "GET"):
        return request.GET
    # As a fallback, assume dict-like
    return getattr(request, "params", {}) or {}

def _is_datetime_field(qs: QuerySet, field_name: str) -> bool:
    """
    Inspect model meta to decide if field_name is a DateTimeField.
    Returns False for DateField and when field not found.
    """
    try:
        field = qs.model._meta.get_field(field_name)
        return field.get_internal_type() == "DateTimeField"
    except Exception:
        return False
    
def search_in_emailuser_fields(search_value: str) -> list[int]:
    """
    Search `search_value` in EmailUser fields: email, first_name, last_name, and full name.
    Returns a list of matching EmailUser IDs.
    """

    if not search_value:
        return []

    search_value = search_value.strip()
    if not search_value:
        return []

    full_name_expr = Concat(
        Coalesce('first_name', Value('')),
        Value(' '),
        Coalesce('last_name', Value('')),
    )

    q = (
        Q(email__icontains=search_value) |
        Q(first_name__icontains=search_value) |
        Q(last_name__icontains=search_value) |
        Q(full_name__icontains=search_value)  # annotated below
    )

    return list(
        EmailUser.objects
        .annotate(full_name=full_name_expr)
        .filter(q)
        .values_list('id', flat=True)
        .distinct()
    )

def search_organisation_properties(search_value, search_abn=False):

    if search_abn:
        q = (
            Q(property_cache__name__icontains=search_value) |
            Q(property_cache__abn__icontains=search_value)
        )
    else:
        q = (
            Q(property_cache__name__icontains=search_value)
        )


    return  list(
        Organisation.objects
        .filter(q)
        .values_list('id', flat=True)
        .distinct()
    )

class AssessorDataSearch(object):

    def __init__(self, lookup_field="canBeEditedByAssessor"):
        self.lookup_field = lookup_field
        self.assessor_data = []

    def extract_assessor_data(self, item, post_data):
        values = []
        res = {"name": item, "assessor": "", "referrals": []}
        for k in post_data:
            if re.match(item, k):
                values.append({k: post_data[k]})
        if values:
            for v in values:
                for k, v in v.items():
                    parts = k.split("{}-".format(item))
                    if len(parts) > 1:
                        # split parts to see if referall
                        ref_parts = parts[1].split("Referral-")
                        if len(ref_parts) > 1:
                            # Referrals
                            res["referrals"].append(
                                {
                                    "value": v,
                                    "email": ref_parts[1],
                                    "full_name": EmailUser.objects.get(
                                        email=ref_parts[1].lower()
                                    ).get_full_name(),
                                }
                            )
                        elif k.split("-")[-1].lower() == "assessor":
                            # Assessor
                            res["assessor"] = v

        return res

    def extract_special_fields(self, item, post_data, file_data, repetition, suffix):
        item_data = {}
        if "name" in item:
            extended_item_name = item["name"]
        else:
            raise Exception("Missing name in item %s" % item["label"])

        if "children" not in item:
            if "conditions" in item:
                for condition in item["conditions"].keys():
                    for child in item["conditions"][condition]:
                        item_data.update(
                            self.extract_special_fields(
                                child, post_data, file_data, repetition, suffix
                            )
                        )

            if item.get(self.lookup_field):
                self.assessor_data.append(
                    self.extract_assessor_data(extended_item_name, post_data)
                )

        else:
            if "repetition" in item:
                item_data = self.generate_item_data_special_field(
                    extended_item_name,
                    item,
                    item_data,
                    post_data,
                    file_data,
                    len(post_data[item["name"]]),
                    suffix,
                )
            else:
                item_data = self.generate_item_data_special_field(
                    extended_item_name, item, item_data, post_data, file_data, 1, suffix
                )

            if "conditions" in item:
                for condition in item["conditions"].keys():
                    for child in item["conditions"][condition]:
                        item_data.update(
                            self.extract_special_fields(
                                child, post_data, file_data, repetition, suffix
                            )
                        )

        return item_data

    def generate_item_data_special_field(
        self, item_name, item, item_data, post_data, file_data, repetition, suffix
    ):
        item_data_list = []
        for rep in range(repetition):
            child_data = {}
            for child_item in item.get("children"):
                child_data.update(
                    self.extract_special_fields(
                        child_item, post_data, file_data, 0, "{}-{}".format(suffix, rep)
                    )
                )
            item_data_list.append(child_data)

            item_data[item["name"]] = item_data_list
        return item_data


class CommentDataSearch(object):

    def __init__(self, lookup_field="canBeEditedByAssessor"):
        self.lookup_field = lookup_field
        self.comment_data = {}

    def extract_comment_data(self, item, post_data):
        res = {}
        values = []
        for k in post_data:
            if re.match(item, k):
                values.append({k: post_data[k]})
        if values:
            for v in values:
                for k, v in v.items():
                    parts = k.split("{}".format(item))
                    if len(parts) > 1:
                        ref_parts = parts[1].split("-comment-field")
                        if len(ref_parts) > 1:
                            res = {"{}".format(item): v}
        return res

    def extract_special_fields(self, item, post_data, file_data, repetition, suffix):
        item_data = {}
        if "name" in item:
            extended_item_name = item["name"]
        else:
            raise Exception("Missing name in item %s" % item["label"])

        if "children" not in item:
            self.comment_data.update(
                self.extract_comment_data(extended_item_name, post_data)
            )

        else:
            if "repetition" in item:
                item_data = self.generate_item_data_special_field(
                    extended_item_name,
                    item,
                    item_data,
                    post_data,
                    file_data,
                    len(post_data[item["name"]]),
                    suffix,
                )
            else:
                item_data = self.generate_item_data_special_field(
                    extended_item_name, item, item_data, post_data, file_data, 1, suffix
                )

        if "conditions" in item:
            for condition in item["conditions"].keys():
                for child in item["conditions"][condition]:
                    item_data.update(
                        self.extract_special_fields(
                            child, post_data, file_data, repetition, suffix
                        )
                    )

        return item_data

    def generate_item_data_special_field(
        self, item_name, item, item_data, post_data, file_data, repetition, suffix
    ):
        item_data_list = []
        for rep in range(repetition):
            child_data = {}
            for child_item in item.get("children"):
                child_data.update(
                    self.extract_special_fields(
                        child_item, post_data, file_data, 0, "{}-{}".format(suffix, rep)
                    )
                )
            item_data_list.append(child_data)

            item_data[item["name"]] = item_data_list
        return item_data


class SpecialFieldsSearch(object):

    def __init__(self, lookable_fields):
        self.lookable_fields = lookable_fields
        self.special_fields = {}

    def extract_special_fields(self, item, post_data, file_data, repetition, suffix):
        item_data = {}
        if "name" in item:
            extended_item_name = item["name"]
        else:
            raise Exception("Missing name in item %s" % item["label"])

        if "children" not in item:
            for f in self.lookable_fields:
                if item["type"] in ["checkbox" "declaration"]:
                    val = None
                    val = item.get(f, None)
                    if val:
                        item_data[f] = extended_item_name in post_data
                        self.special_fields.update(item_data)
                else:
                    if extended_item_name in post_data:
                        val = None
                        val = item.get(f, None)
                        if val:
                            if item["type"] == "multi-select":
                                item_data[f] = ",".join(
                                    post_data.getlist(extended_item_name)
                                )
                            else:
                                item_data[f] = post_data.get(extended_item_name)
                            self.special_fields.update(item_data)
        else:
            if "repetition" in item:
                item_data = self.generate_item_data_special_field(
                    extended_item_name,
                    item,
                    item_data,
                    post_data,
                    file_data,
                    len(post_data[item["name"]]),
                    suffix,
                )
            else:
                item_data = self.generate_item_data_special_field(
                    extended_item_name, item, item_data, post_data, file_data, 1, suffix
                )

        if "conditions" in item:
            for condition in item["conditions"].keys():
                for child in item["conditions"][condition]:
                    item_data.update(
                        self.extract_special_fields(
                            child, post_data, file_data, repetition, suffix
                        )
                    )

        return item_data

    def generate_item_data_special_field(
        self, item_name, item, item_data, post_data, file_data, repetition, suffix
    ):
        item_data_list = []
        for rep in range(repetition):
            child_data = {}
            for child_item in item.get("children"):
                child_data.update(
                    self.extract_special_fields(
                        child_item, post_data, file_data, 0, "{}-{}".format(suffix, rep)
                    )
                )
            item_data_list.append(child_data)

            item_data[item["name"]] = item_data_list
        return item_data


@basic_exception_handler
@transaction.atomic
def save_park_activity_data(
    instance, select_parks_activities, request, assessor_save=False
):
    # if select_parks_activities or len(select_parks_activities) == 0:
    if select_parks_activities is None:
        return

    if len(select_parks_activities) == 0:
        new_parks = instance.parks.filter(park__park_type="land")

        if not assessor_save:
            internal_parks = instance.parks.filter(
                park__park_type="land",
                park__visible_to_external=False,
            )
            internal_park_ids = set(p.park_id for p in internal_parks)

            for park in new_parks:
                if park.park_id not in internal_park_ids:
                    park_id = park.park_id
                    park.delete()
                    instance.log_user_action(
                        ProposalUserAction.ACTION_UNLINK_PARK.format(
                            park_id, instance.id
                        ),
                        request.user,
                    )
        else:
            for park in new_parks:
                park_id = park.park_id
                park.delete()
                instance.log_user_action(
                    ProposalUserAction.ACTION_UNLINK_PARK.format(
                        park_id, instance.id
                    ),
                    request.user,
                )
        return

    # current_parks=instance.parks.all()
    selected_parks = []
    for item in select_parks_activities:
        if item["park"]:
            selected_parks.append(item["park"])
            try:
                # Check if PrposalPark record already exists. If exists, check for activities
                park = ProposalPark.objects.get(park=item["park"], proposal=instance)
                current_activities = park.land_activities.all()
                current_activities_id = [a.activity_id for a in current_activities]
                # Get the access records related to ProposalPark
                current_access = park.access_types.all()
                current_access_id = [a.access_type_id for a in current_access]
                if item["activities"]:
                    for a in item["activities"]:
                        if a in current_activities_id:
                            # If the activity already exists but is not permitted in is park (e.g. removed from admin) then remove it otherwise create the record.
                            if a not in park.park.allowed_activities_ids:
                                ppa = ProposalParkActivity.objects.filter(
                                    proposal_park=park, activity_id=a
                                )
                                if ppa.exists():
                                    logger.info(f"Found activity {ppa.first()} not allowed for this park: {park}. Deleting it from proposal {instance}.")
                                    ppa.delete()
                        else:
                            try:
                                if a not in park.park.allowed_activities_ids:
                                    # raise Exception('Activity not allowed for this park')
                                    pass
                                else:
                                    activity = Activity.objects.get(id=a)
                                    ProposalParkActivity.objects.create(
                                        proposal_park=park,
                                        activity=activity,
                                    )
                                    instance.log_user_action(
                                        ProposalUserAction.ACTION_LINK_ACTIVITY.format(
                                            activity.id, park.park.id
                                        ),
                                        request.user,
                                    )
                            except:
                                raise
                if item["access"]:
                    for a in item["access"]:
                        if a in current_access_id:
                            # if access type already exists then pass otherwise create the record.
                            pass
                        else:
                            try:
                                if a not in park.park.allowed_access_ids:
                                    # raise Exception('Activity not allowed for this park')
                                    pass
                                else:
                                    access = AccessType.objects.get(id=a)
                                    ProposalParkAccess.objects.create(
                                        proposal_park=park,
                                        access_type=access,
                                    )
                                    instance.log_user_action(
                                        ProposalUserAction.ACTION_LINK_ACCESS.format(
                                            access.id, park.park.id
                                        ),
                                        request.user,
                                    )
                            except:
                                raise
            except ProposalPark.DoesNotExist:
                try:
                    # If ProposalPark does not exists then create a new record and activities for it.
                    park_instance = Park.objects.get(id=item["park"])
                    park = ProposalPark.objects.create(
                        park=park_instance, proposal=instance
                    )
                    instance.log_user_action(
                        ProposalUserAction.ACTION_LINK_PARK.format(
                            park.park.id, instance.id
                        ),
                        request.user,
                    )
                    current_activities = []
                    for a in item["activities"]:
                        try:
                            if a not in park.park.allowed_activities_ids:
                                # raise Exception('Activity not allowed for this park')
                                pass
                            else:
                                activity = Activity.objects.get(id=a)
                                ProposalParkActivity.objects.create(
                                    proposal_park=park,
                                    activity=activity,
                                )
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ACTIVITY.format(
                                        activity.id, park.park.id
                                    ),
                                    request.user,
                                )
                        except:
                            raise
                    for a in item["access"]:
                        try:
                            if a not in park.park.allowed_access_ids:
                                # raise Exception('Activity not allowed for this park')
                                pass
                            else:
                                access = AccessType.objects.get(id=a)
                                ProposalParkAccess.objects.create(
                                    proposal_park=park,
                                    access_type=access,
                                )
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ACCESS.format(
                                        access.id, park.park.id
                                    ),
                                    request.user,
                                )
                        except:
                            raise
                except:
                    raise
            # compare all activities (new+old) with the list of activities selected activities to get
            # the list of deleted activities.
            new_activities = park.land_activities.all()
            new_activities_id = set(a.activity_id for a in new_activities)
            diff_activity = set(new_activities_id).difference(set(item["activities"]))
            for d in diff_activity:
                act = ProposalParkActivity.objects.get(
                    activity_id=d, proposal_park=park
                )
                act.delete()
                instance.log_user_action(
                    ProposalUserAction.ACTION_UNLINK_ACTIVITY.format(d, park.park.id),
                    request.user,
                )
            new_access = park.access_types.all()
            new_access_id = set(a.access_type_id for a in new_access)
            diff_access = set(new_access_id).difference(set(item["access"]))
            for d in diff_access:
                acc = ProposalParkAccess.objects.get(
                    access_type_id=d, proposal_park=park
                )
                acc.delete()
                instance.log_user_action(
                    ProposalUserAction.ACTION_UNLINK_ACCESS.format(d, park.park.id),
                    request.user,
                )
    new_parks = instance.parks.filter(park__park_type="land")
    new_parks_id = set(p.park_id for p in new_parks)
    if not assessor_save:
        internal_parks = instance.parks.filter(
            park__park_type="land", park__visible_to_external=False
        )
        if internal_parks:
            for p in internal_parks:
                selected_parks.append(p.park_id)
            # selected_parks.append(p.park_id for p in internal_parks)
    diff_parks = set(new_parks_id).difference(set(selected_parks))
    for d in diff_parks:
        pk = ProposalPark.objects.get(park=d, proposal=instance)
        pk.delete()
        instance.log_user_action(
            ProposalUserAction.ACTION_UNLINK_PARK.format(d, instance.id),
            request.user,
        )


@basic_exception_handler
@transaction.atomic
def save_trail_section_activity_data(instance, select_trails_activities, request):
    def _to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if select_trails_activities is None:
        return

    # Clearing all selected trails must remove all stored trail/section/activity data.
    if len(select_trails_activities) == 0:
        for existing_trail in instance.trails.all():
            trail_id = existing_trail.trail_id
            existing_trail.delete()
            instance.log_user_action(
                ProposalUserAction.ACTION_UNLINK_TRAIL.format(trail_id, instance.id),
                request.user,
            )
        return

    selected_trail_ids = set()

    for item in select_trails_activities:
        trail_id = _to_int(item.get("trail"))
        if not trail_id:
            continue

        selected_trail_ids.add(trail_id)

        trail, trail_created = ProposalTrail.objects.get_or_create(
            trail_id=trail_id,
            proposal=instance,
            defaults={"trail": Trail.objects.get(id=trail_id)},
        )
        if trail_created:
            instance.log_user_action(
                ProposalUserAction.ACTION_LINK_TRAIL.format(trail.trail.id, instance.id),
                request.user,
            )

        selected_section_ids = set()
        section_payloads = item.get("activities") or []

        for section_payload in section_payloads:
            section_id = _to_int(section_payload.get("section"))
            if not section_id:
                continue

            selected_section_ids.add(section_id)

            section, section_created = ProposalTrailSection.objects.get_or_create(
                proposal_trail=trail,
                section_id=section_id,
                defaults={"section": Section.objects.get(id=section_id)},
            )
            if section_created:
                instance.log_user_action(
                    ProposalUserAction.ACTION_LINK_SECTION.format(
                        section.section.id,
                        trail.trail.id,
                    ),
                    request.user,
                )

            requested_activity_ids = {
                _to_int(activity_id)
                for activity_id in (section_payload.get("activities") or [])
            }
            requested_activity_ids.discard(None)

            # Keep only activities permitted for the selected trail.
            allowed_activity_ids = set(trail.trail.allowed_activities_ids)
            requested_activity_ids = requested_activity_ids.intersection(
                allowed_activity_ids
            )

            existing_activity_ids = set(
                section.trail_activities.values_list("activity_id", flat=True)
            )

            for activity_id in requested_activity_ids.difference(existing_activity_ids):
                activity = Activity.objects.get(id=activity_id)
                ProposalTrailSectionActivity.objects.create(
                    trail_section=section,
                    activity=activity,
                )
                instance.log_user_action(
                    ProposalUserAction.ACTION_LINK_ACTIVITY_SECTION.format(
                        activity.id,
                        section.section.id,
                        trail.trail.id,
                    ),
                    request.user,
                )

            for activity_id in existing_activity_ids.difference(requested_activity_ids):
                ProposalTrailSectionActivity.objects.filter(
                    trail_section=section,
                    activity_id=activity_id,
                ).delete()
                instance.log_user_action(
                    ProposalUserAction.ACTION_UNLINK_ACTIVITY_SECTION.format(
                        activity_id,
                        section.section.id,
                        trail.trail.id,
                    ),
                    request.user,
                )

        existing_section_ids = set(
            trail.sections.values_list("section_id", flat=True)
        )
        for section_id in existing_section_ids.difference(selected_section_ids):
            ProposalTrailSection.objects.filter(
                proposal_trail=trail,
                section_id=section_id,
            ).delete()
            instance.log_user_action(
                ProposalUserAction.ACTION_UNLINK_SECTION.format(
                    section_id,
                    trail.trail.id,
                ),
                request.user,
            )

    existing_trail_ids = set(instance.trails.values_list("trail_id", flat=True))
    for trail_id in existing_trail_ids.difference(selected_trail_ids):
        ProposalTrail.objects.filter(proposal=instance, trail_id=trail_id).delete()
        instance.log_user_action(
            ProposalUserAction.ACTION_UNLINK_TRAIL.format(trail_id, instance.id),
            request.user,
        )


@basic_exception_handler
@transaction.atomic
def save_park_zone_activity_data(
    instance, marine_parks_activities, request, assessor_save=False
):
    # if marine_parks_activities or len(marine_parks_activities) == 0:
    if not marine_parks_activities and not len(marine_parks_activities):
        return

    parkzone_activity = []
    # current_parks=instance.parks.all()
    selected_parks = []
    # print("selected_parks",selected_parks)
    for item in marine_parks_activities:
        if item["park"]:
            selected_parks.append(item["park"])
            selected_zones = []
            try:
                # Check if PrposalPark record already exists. If exists, check for zones
                park = ProposalPark.objects.get(park=item["park"], proposal=instance)
                current_zones = park.zones.all()
                current_zones_ids = [a.zone_id for a in current_zones]
                if item["activities"]:
                    for a in item["activities"]:
                        if a["zone"]:
                            selected_zones.append(a["zone"])
                            if a["zone"] in current_zones_ids:
                                zone = ProposalParkZone.objects.get(
                                    proposal_park=park, zone=a["zone"]
                                )
                                current_activities = zone.park_activities.all()
                                current_activities_id = [
                                    s.activity_id for s in current_activities
                                ]
                                allowed_act_ids = list(
                                    set(zone.zone.allowed_activities_ids).intersection(
                                        a["activities"]
                                    )
                                )

                                [
                                    ProposalParkZoneActivity.objects.get_or_create(
                                        park_zone=zone,
                                        activity_id=act_id,
                                    )
                                    for act_id in allowed_act_ids
                                ]
                                # parkzone_activity=[ProposalParkZoneActivity(park_zone=zone, activity_id=act_id) for act_id in allowed_act_ids]
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ACTIVITY_ZONE.format(
                                        ", ".join(map(str, allowed_act_ids)),
                                        zone.zone.id,
                                        park.park.id,
                                    ),
                                    request.user,
                                )

                                if "access_point" in a:
                                    zone.access_point = a["access_point"]
                                    zone.save()
                            else:
                                zone_instance = Zone.objects.get(id=a["zone"])
                                zone = ProposalParkZone.objects.create(
                                    proposal_park=park,
                                    zone=zone_instance,
                                )
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ZONE.format(
                                        zone.zone.id, park.park.id
                                    ),
                                    request.user,
                                )
                                allowed_act_ids = list(
                                    set(zone.zone.allowed_activities_ids).intersection(
                                        a["activities"]
                                    )
                                )

                                [
                                    ProposalParkZoneActivity.objects.get_or_create(
                                        park_zone=zone,
                                        activity_id=act_id,
                                    )
                                    for act_id in allowed_act_ids
                                ]
                                # parkzone_activity=[ProposalParkZoneActivity(park_zone=zone, activity_id=act_id) for act_id in allowed_act_ids]
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ACTIVITY_ZONE.format(
                                        ", ".join(map(str, allowed_act_ids)),
                                        zone.zone.id,
                                        park.park.id,
                                    ),
                                    request.user,
                                )
                                if "access_point" in a:
                                    zone.access_point = a["access_point"]
                                    zone.save()
                            new_activities = zone.park_activities.all()
                            new_activities_id = set(
                                n.activity_id for n in new_activities
                            )
                            diff_activity = set(new_activities_id).difference(
                                set(a["activities"])
                            )
                            # print("park:",park.park_id,"zone:",zone.zone_id,"new_activities:",new_activities_id, "diff:", diff_activity)
                            for d in diff_activity:
                                act = ProposalParkZoneActivity.objects.get(
                                    activity_id=d, park_zone=zone
                                )
                                act.delete()
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_UNLINK_ACTIVITY_ZONE.format(
                                        d, zone.zone.id, park.park.id
                                    ),
                                    request.user,
                                )

            except ProposalPark.DoesNotExist:
                try:
                    # If ProposalPark does not exists then create a new record and activities for it.
                    park_instance = Park.objects.get(id=item["park"])
                    park = ProposalPark.objects.create(
                        park=park_instance, proposal=instance
                    )
                    instance.log_user_action(
                        ProposalUserAction.ACTION_LINK_PARK.format(
                            park.park.id, instance.id
                        ),
                        request.user,
                    )
                    current_zones = []
                    if item["activities"]:
                        for a in item["activities"]:
                            if a["zone"]:
                                selected_zones.append(a["zone"])
                                zone_instance = Zone.objects.get(id=a["zone"])
                                zone = ProposalParkZone.objects.create(
                                    proposal_park=park,
                                    zone=zone_instance,
                                )
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ZONE.format(
                                        zone.zone.id, park.park.id
                                    ),
                                    request.user,
                                )
                                allowed_act_ids = list(
                                    set(zone.zone.allowed_activities_ids).intersection(
                                        a["activities"]
                                    )
                                )

                                [
                                    ProposalParkZoneActivity.objects.get_or_create(
                                        park_zone=zone,
                                        activity_id=act_id,
                                    )
                                    for act_id in allowed_act_ids
                                ]
                                # parkzone_activity=[ProposalParkZoneActivity(park_zone=zone, activity_id=act_id) for act_id in allowed_act_ids]
                                instance.log_user_action(
                                    ProposalUserAction.ACTION_LINK_ACTIVITY_ZONE.format(
                                        ", ".join(map(str, allowed_act_ids)),
                                        zone.zone.id,
                                        park.park.id,
                                    ),
                                    request.user,
                                )

                                if "access_point" in a:
                                    zone.access_point = a["access_point"]
                                    zone.save()
                except:
                    raise
            # compare all zones (new+old) with the list of zones selected to get
            # the list of deleted zones.
            new_zones = park.zones.all()
            new_zones_ids = set(a.zone_id for a in new_zones)
            diff_zones = set(new_zones_ids).difference(set(selected_zones))
            # print("park:",park.park_id, "new_zones:", new_zones_ids,"diff_zones:", diff_zones)
            for d in diff_zones:
                pk = ProposalParkZone.objects.get(zone=d, proposal_park=park)
                pk.delete()
                instance.log_user_action(
                    ProposalUserAction.ACTION_UNLINK_ZONE.format(d, park.park.id),
                    request.user,
                )
    new_parks = instance.parks.filter(park__park_type="marine")
    new_parks_id = set(p.park_id for p in new_parks)
    # print("new_parks", new_parks_id, "diff:", diff_parks)
    if not assessor_save:
        internal_parks = instance.parks.filter(
            park__park_type="marine", park__visible_to_external=False
        )
        if internal_parks:
            for p in internal_parks:
                selected_parks.append(p.park_id)
    diff_parks = set(new_parks_id).difference(set(selected_parks))
    for d in diff_parks:
        pk = ProposalPark.objects.get(park=d, proposal=instance)
        pk.delete()
        instance.log_user_action(
            ProposalUserAction.ACTION_UNLINK_PARK.format(d, instance.id),
            request.user,
        )


def save_proponent_data(instance, request, viewset, parks=None, trails=None):
    if instance.application_type.name == ApplicationType.FILMING:
        save_proponent_data_filming(instance, request, viewset, parks=None, trails=None)
    elif instance.application_type.name == ApplicationType.EVENT:
        save_proponent_data_event(instance, request, viewset, parks=None, trails=None)
    else:
        save_proponent_data_tclass(instance, request, viewset, parks=None, trails=None)


from commercialoperator.components.main.models import ApplicationType
from commercialoperator.components.proposals.models import ProposalFilmingOtherDetails
from commercialoperator.components.proposals.serializers_filming import (
    ProposalFilmingOtherDetailsSerializer,
    ProposalFilmingActivitySerializer,
    ProposalFilmingAccessSerializer,
    ProposalFilmingEquipmentSerializer,
)


@transaction.atomic
def save_proponent_data_filming(instance, request, viewset, parks=None, trails=None):
    data = {}

    try:
        schema = request.data.get("schema")
    except:
        schema = request.POST.get("schema")
    import json

    sc = json.loads(schema)
    filming_activity_data = sc["filming_activity"]
    filming_access_data = sc["filming_access"]
    filming_equipment_data = sc["filming_equipment"]
    filming_other_details_data = sc["filming_other_details"]

    # save Filming activity data
    serializer = ProposalFilmingActivitySerializer(
        instance.filming_activity, data=filming_activity_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming access data
    serializer = ProposalFilmingAccessSerializer(
        instance.filming_access, data=filming_access_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming equipment data
    serializer = ProposalFilmingEquipmentSerializer(
        instance.filming_equipment, data=filming_equipment_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming other details data
    serializer = ProposalFilmingOtherDetailsSerializer(
        instance.filming_other_details, data=filming_other_details_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    ProposalFilmingOtherDetails.objects.update_or_create(proposal=instance)
    serializer = SaveProposalSerializer(instance, data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()


@transaction.atomic
def save_proponent_data_event(instance, request, viewset, parks=None, trails=None):
    data = {}

    try:
        schema = request.data.get("schema")
    except:
        schema = request.POST.get("schema")
    import json

    sc = json.loads(schema)
    event_activity_data = sc["event_activity"]
    event_vehicles_vessels_data = sc["event_vehicles_vessels"]
    # filming_access_data=sc['filming_access']
    event_management_data = sc["event_management"]
    events_other_details_data = sc["event_other_details"]
    try:
        select_trails_activities = json.loads(
            request.data.get("selected_trails_activities")
        )
    except:
        select_trails_activities = json.loads(
            request.POST.get("selected_trails_activities", None)
        )

    # print select_trails_activities
    # save Event Activity tab data
    serializer = ProposalEventActivitiesSerializer(
        instance.event_activity, data=event_activity_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event Vehicle Vessels data
    serializer = ProposalEventVehiclesVesselsSerializer(
        instance.event_vehicles_vessels, data=event_vehicles_vessels_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event Management data
    serializer = ProposalEventManagementSerializer(
        instance.event_management, data=event_management_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event other details data
    serializer = ProposalEventOtherDetailsSerializer(
        instance.event_other_details, data=events_other_details_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    if select_trails_activities or len(select_trails_activities) == 0:
        try:

            save_trail_section_activity_data(
                instance, select_trails_activities, request
            )

        except:
            raise

    serializer = SaveProposalSerializer(instance, data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()


@transaction.atomic
def save_proponent_data_tclass(instance, request, viewset, parks=None, trails=None):
    data = {}

    try:
        schema = request.data.get("schema")
    except:
        schema = request.POST.get("schema")
    import json

    sc = json.loads(schema)
    other_details_data = sc["other_details"]

    if instance.is_amendment_proposal or instance.pending_amendment_request:
        other_details_data["preferred_licence_period"] = (
            instance.other_details.preferred_licence_period
        )
    serializer = ProposalOtherDetailsSerializer(
        instance.other_details, data=other_details_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    try:
        select_parks_activities = json.loads(
            request.data.get("selected_parks_activities")
        )
        select_trails_activities = json.loads(
            request.data.get("selected_trails_activities")
        )
        marine_parks_activities = json.loads(
            request.data.get("marine_parks_activities")
        )
    except:
        select_parks_activities = json.loads(
            request.POST.get("selected_parks_activities", None)
        )
        select_trails_activities = json.loads(
            request.POST.get("selected_trails_activities", None)
        )
        marine_parks_activities = json.loads(
            request.POST.get("marine_parks_activities", None)
        )

    ProposalOtherDetails.objects.update_or_create(proposal=instance)
    serializer = SaveProposalSerializer(instance, data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if "accreditations" in other_details_data:
        accreditation_types = instance.other_details.accreditations.values_list(
            "accreditation_type", flat=True
        )
        for acc in other_details_data["accreditations"]:
            if "id" in acc:
                acc_qs = instance.other_details.accreditations.filter(id=acc["id"])

                if acc_qs and "is_deleted" in acc and acc["is_deleted"] == True:
                    acc_qs[0].delete()

                elif acc["accreditation_type"] in accreditation_types:
                    try:
                        instance.other_details.accreditations.filter(
                            id=acc["id"]
                        ).update(
                            accreditation_type=acc["accreditation_type"],
                            comments=acc["comments"],
                            accreditation_expiry=(
                                datetime.strptime(
                                    acc["accreditation_expiry"], "%Y-%m-%d"
                                ).date()
                                if acc["accreditation_expiry"]
                                else None
                            ),
                        )
                    except Exception as e:
                        logger.error(
                            "An error occurred while updating Accreditations {}".format(
                                e
                            )
                        )
                else:
                    serializer = ProposalAccreditationSerializer(data=acc)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()

            elif acc["accreditation_type"] not in accreditation_types:
                serializer = ProposalAccreditationSerializer(data=acc)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                logger.warning(
                    "Possible duplicate Accreditation Type for Application {}".format(
                        instance.lodgement_number
                    )
                )
    # Save information standards data
    if "information_standards" in other_details_data:
        information_standard_types = (
            instance.other_details.information_standards.values_list(
                "information_standard_type", flat=True
            )
        )
        for info in other_details_data["information_standards"]:
            # print info
            if "id" in info:
                # info_qs = ProposalInformationStandard.objects.filter(id=info['id'])
                info_qs = instance.other_details.information_standards.filter(
                    id=info["id"]
                )

                if info_qs and "is_deleted" in info and info["is_deleted"] == True:
                    info_qs[0].delete()

                elif info["information_standard_type"] in information_standard_types:
                    try:
                        instance.other_details.information_standards.filter(
                            id=info["id"]
                        ).update(
                            information_standard_type=info[
                                "information_standard_type"
                            ],
                            information_comments=info["comments"],
                        )
                    except Exception as e:
                        logger.error(
                            "An error occurred while updating Information Standards {}".format(
                                e
                            )
                        )
                else:
                    serializer = ProposalInformationStandardSerializer(data=info)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    # ProposalAccreditation.objects.create(
                    #    id=acc['id'],
                    #    accreditation_type=acc['accreditation_type'],
                    #    comments = acc['comments'],
                    #    accreditation_expiry = datetime.strptime(acc['accreditation_expiry'], "%d/%m/%Y").date(),
                    # )

            elif info["information_standard_type"] not in information_standard_types:
                serializer = ProposalInformationStandardSerializer(data=info)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                logger.warning(
                    "Possible duplicate Information Standard Type for Application {}".format(
                        instance.lodgement_number
                    )
                )

    # Save emission standards data
    if "emission_standards" in other_details_data:
        emission_standard_types = instance.other_details.emission_standards.values_list(
            "emission_standard_type", flat=True
        )
        for info in other_details_data["emission_standards"]:
            # print info
            if "id" in info:
                # info_qs = ProposalEmissionStandard.objects.filter(id=info['id'])
                info_qs = instance.other_details.emission_standards.filter(
                    id=info["id"]
                )

                if info_qs and "is_deleted" in info and info["is_deleted"] == True:
                    info_qs[0].delete()

                elif info["emission_standard_type"] in emission_standard_types:
                    try:
                        instance.other_details.emission_standards.filter(
                            id=info["id"]
                        ).update(
                            emission_standard_type=info["emission_standard_type"],
                            emission_comments=info["comments"],
                        )
                    except Exception as e:
                        logger.error(
                            "An error occurred while updating Emission Standards {}".format(
                                e
                            )
                        )
                else:
                    serializer = ProposalEmissionStandardSerializer(data=info)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    # ProposalAccreditation.objects.create(
                    #    id=acc['id'],
                    #    accreditation_type=acc['accreditation_type'],
                    #    comments = acc['comments'],
                    #    accreditation_expiry = datetime.strptime(acc['accreditation_expiry'], "%d/%m/%Y").date(),
                    # )

            elif info["emission_standard_type"] not in emission_standard_types:
                serializer = ProposalEmissionStandardSerializer(data=info)
                serializer.is_valid(raise_exception=True)
                serializer.save()
            else:
                logger.warning(
                    "Possible duplicate Emission Standard Type for Application {}".format(
                        instance.lodgement_number
                    )
                )
    if select_parks_activities or len(select_parks_activities) == 0:
        try:

            save_park_activity_data(instance, select_parks_activities, request)

        except:
            raise

    if select_trails_activities or len(select_trails_activities) == 0:
        try:

            save_trail_section_activity_data(
                instance, select_trails_activities, request
            )

        except:
            raise

    if marine_parks_activities or len(marine_parks_activities) == 0:
        try:
            save_park_zone_activity_data(instance, marine_parks_activities, request)
        except:
            raise


@transaction.atomic
def save_assessor_data(instance, request, viewset):
    try:
        if instance.application_type.name == ApplicationType.FILMING:
            save_assessor_data_filming(instance, request, viewset)
        if instance.application_type.name == ApplicationType.TCLASS:
            save_assessor_data_tclass(instance, request, viewset)
        if instance.application_type.name == ApplicationType.EVENT:
            save_assessor_data_event(instance, request, viewset)
    except:
        raise


@transaction.atomic
def proposal_submit(proposal, request=None):
    if proposal.can_user_edit:
        if request and request.user and isinstance(request.user,EmailUser):
            if not proposal.submitter:
                proposal.submitter = request.user #NOTE: submitter should already be set
                proposal.save()
            #Same org, different submitter
            if proposal.org_applicant:
                if OrganisationContact.objects.filter(organisation=proposal.org_applicant,email=request.user.email).exists():
                    proposal.submitter = request.user
                    proposal.save()
        proposal.lodgement_date = timezone.now()
        proposal.training_completed = True
        if proposal.amendment_requests:
            qs = proposal.amendment_requests.filter(status="requested")
            if qs:
                for q in qs:
                    q.status = "amended"
                    q.save()

        # Create a log entry for the proposal
        proposal.log_user_action(
            ProposalUserAction.ACTION_LODGE_APPLICATION.format(proposal.id), proposal.submitter
        )
        # Create a log entry for the organisation
        applicant_field = getattr(proposal, proposal.applicant_field)
        applicant_field.log_user_action(
            ProposalUserAction.ACTION_LODGE_APPLICATION.format(proposal.id), proposal.submitter
        )
        #NOTE: request=None works fine with these email functions
        ret1 = send_submit_email_notification(request, proposal)
        ret2 = send_external_submit_email_notification(request, proposal)

        if ret1 and ret2:
            proposal.processing_status = "with_assessor"
            proposal.customer_status = "with_assessor"
            proposal.documents.all().update(can_delete=False, can_hide=True)
            proposal.required_documents.all().update(can_delete=False, can_hide=True)
            proposal.save()
        else:
            raise ValidationError(
                "An error occurred while submitting proposal (Submit email notifications failed)"
            )
        # Create assessor checklist with the current assessor_list type questions
        # Assessment instance already exits then skip.
        try:
            assessor_assessment = ProposalAssessment.objects.get(
                proposal=proposal, referral_group=None, referral_assessment=False
            )
        except ProposalAssessment.DoesNotExist:
            assessor_assessment = ProposalAssessment.objects.create(
                proposal=proposal, referral_group=None, referral_assessment=False
            )
            checklist = ChecklistQuestion.objects.filter(
                list_type="assessor_list",
                application_type=proposal.application_type,
                obsolete=False,
            )
            for chk in checklist:
                try:
                    chk_instance = ProposalAssessmentAnswer.objects.get(
                        question=chk, assessment=assessor_assessment
                    )
                except ProposalAssessmentAnswer.DoesNotExist:
                    chk_instance = ProposalAssessmentAnswer.objects.create(
                        question=chk, assessment=assessor_assessment
                    )

        return proposal


def is_payment_officer(user):
    from commercialoperator.components.proposals.models import PaymentOfficerGroup

    try:
        group = PaymentOfficerGroup.objects.get(default=True)
    except PaymentOfficerGroup.DoesNotExist:
        group = None
    if group:
        if user in group.members.all():
            return True
    return False


@transaction.atomic
def save_assessor_data_filming(instance, request, viewset):
    try:
        schema = request.data.get("schema")
    except:
        schema = request.POST.get("schema")
    import json

    sc = json.loads(schema)
    filming_activity_data = sc["filming_activity"]
    filming_access_data = sc["filming_access"]
    filming_equipment_data = sc["filming_equipment"]
    filming_other_details_data = sc["filming_other_details"]

    # save Filming activity data
    serializer = ProposalFilmingActivitySerializer(
        instance.filming_activity, data=filming_activity_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming access data
    serializer = ProposalFilmingAccessSerializer(
        instance.filming_access, data=filming_access_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming equipment data
    serializer = ProposalFilmingEquipmentSerializer(
        instance.filming_equipment, data=filming_equipment_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # save Filming other details data
    serializer = ProposalFilmingOtherDetailsSerializer(
        instance.filming_other_details, data=filming_other_details_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    # To allow update following 'Back to assessor', to start_date and expiry date for activity
    for district_proposal in instance.district_proposals.all():
        if district_proposal.proposed_issuance_approval:
            if instance.filming_activity.commencement_date:
                district_proposal.proposed_issuance_approval["start_date"] = (
                    instance.filming_activity.commencement_date.strftime("%d/%m/%Y")
                )
                district_proposal.save()
            if instance.filming_activity.completion_date:
                district_proposal.proposed_issuance_approval["expiry_date"] = (
                    instance.filming_activity.completion_date.strftime("%d/%m/%Y")
                )
                district_proposal.save()

    serializer = SaveInternalFilmingProposalSerializer(instance, sc, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    for f in request.FILES:
        try:
            document = instance.documents.get(input_name=f)
        except ProposalDocument.DoesNotExist:
            document = instance.documents.get_or_create(input_name=f)[0]
        document.name = str(request.FILES[f])
        if document._file and os.path.isfile(document._file.path):
            os.remove(document._file.path)
        document._file = request.FILES[f]
        document.save()
    # End Save Documents


@transaction.atomic
def save_assessor_data_event(instance, request, viewset):
    try:
        schema = request.data.get("schema")
    except:
        schema = request.POST.get("schema")
    import json

    sc = json.loads(schema)
    event_activity_data = sc["event_activity"]
    event_vehicles_vessels_data = sc["event_vehicles_vessels"]
    event_management_data = sc["event_management"]
    events_other_details_data = sc["event_other_details"]
    try:
        select_trails_activities = json.loads(
            request.data.get("selected_trails_activities")
        )
    except:
        select_trails_activities = json.loads(
            request.POST.get("selected_trails_activities", None)
        )

    # save Event Activity tab data
    serializer = ProposalEventActivitiesSerializer(
        instance.event_activity, data=event_activity_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event Vehicle Vessels data
    serializer = ProposalEventVehiclesVesselsSerializer(
        instance.event_vehicles_vessels, data=event_vehicles_vessels_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event Management data
    serializer = ProposalEventManagementSerializer(
        instance.event_management, data=event_management_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # save Event other details data
    serializer = ProposalEventOtherDetailsSerializer(
        instance.event_other_details, data=events_other_details_data
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    if select_trails_activities or len(select_trails_activities) == 0:
        try:

            save_trail_section_activity_data(
                instance, select_trails_activities, request
            )

        except:
            raise

    # To allow update following 'Back to assessor', to start_date and expiry date for activity
    if instance.proposed_issuance_approval:
        if instance.event_activity.commencement_date:
            instance.proposed_issuance_approval["start_date"] = (
                instance.event_activity.commencement_date.strftime("%d/%m/%Y")
            )
        if instance.event_activity.completion_date:
            instance.proposed_issuance_approval["expiry_date"] = (
                instance.event_activity.completion_date.strftime("%d/%m/%Y")
            )

    serializer = SaveInternalEventProposalSerializer(instance, sc, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    for f in request.FILES:
        try:
            document = instance.documents.get(input_name=f)
        except ProposalDocument.DoesNotExist:
            document = instance.documents.get_or_create(input_name=f)[0]
        document.name = str(request.FILES[f])
        if document._file and os.path.isfile(document._file.path):
            os.remove(document._file.path)
        document._file = request.FILES[f]
        document.save()
    # End Save Documents


@transaction.atomic
def save_assessor_data_tclass(instance, request, viewset):
    data = {}
    serializer = SaveProposalSerializer(instance, data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # Save activities
    import json

    assessor_save = True
    try:
        select_parks_activities = json.loads(
            request.data.get("selected_parks_activities")
        )
        select_trails_activities = json.loads(
            request.data.get("selected_trails_activities")
        )
        marine_parks_activities = json.loads(
            request.data.get("marine_parks_activities")
        )
    except:
        select_parks_activities = request.POST.get("selected_parks_activities", None)
        if select_parks_activities:
            select_parks_activities = json.loads(select_parks_activities)
        select_trails_activities = request.POST.get("selected_trails_activities", None)
        if select_trails_activities:
            select_trails_activities = json.loads(select_trails_activities)
        marine_parks_activities = request.POST.get("marine_parks_activities", None)
        if marine_parks_activities:
            marine_parks_activities = json.loads(marine_parks_activities)
    if select_parks_activities or len(select_parks_activities) == 0:
        try:
            save_park_activity_data(
                instance, select_parks_activities, request, assessor_save
            )
        except:
            raise
    if select_trails_activities or len(select_trails_activities) == 0:
        try:
            save_trail_section_activity_data(
                instance, select_trails_activities, request
            )
        except:
            raise
    if marine_parks_activities or len(marine_parks_activities) == 0:
        try:
            save_park_zone_activity_data(
                instance, marine_parks_activities, request, assessor_save
            )
        except:
            raise
    # Save Documents
    for f in request.FILES:
        try:
            document = instance.documents.get(input_name=f)
        except ProposalDocument.DoesNotExist:
            document = instance.documents.get_or_create(input_name=f)[0]
        document.name = str(request.FILES[f])
        if document._file and os.path.isfile(document._file.path):
            os.remove(document._file.path)
        document._file = request.FILES[f]
        document.save()
    # End Save Documents


from commercialoperator.components.proposals.models import (
    Proposal,
    Referral,
    AmendmentRequest,
    ProposalDeclinedDetails,
)
from commercialoperator.components.approvals.models import Approval
from commercialoperator.components.compliances.models import Compliance
from commercialoperator.components.bookings.models import ApplicationFee, Booking

from commercialoperator.components.proposals import email as proposal_email
from commercialoperator.components.approvals import email as approval_email
from commercialoperator.components.compliances import email as compliance_email
from commercialoperator.components.bookings import email as booking_email


def test_proposal_emails(request):
    """Script to test all emails (listed below) from the models"""
    from ledger_api_client.ledger_models import Invoice

    # setup
    if not (settings.PRODUCTION_EMAIL):
        recipients = [request.user.email]
        # proposal = Proposal.objects.last()
        approval = Approval.objects.filter(migrated=False).last()
        proposal = approval.current_proposal
        referral = Referral.objects.last()
        amendment_request = AmendmentRequest.objects.last()
        reason = "Not enough information"
        proposal_decline = ProposalDeclinedDetails.objects.last()
        compliance = Compliance.objects.last()

        application_fee = ApplicationFee.objects.last()
        api = Invoice.objects.get(
            reference=application_fee.application_fee_invoices.last().invoice_reference
        )

        booking = Booking.objects.last()
        bi = Invoice.objects.get(reference=booking.invoices.last().invoice_reference)

        proposal_email.send_qaofficer_email_notification(
            proposal, recipients, request, reminder=False
        )
        proposal_email.send_qaofficer_complete_email_notification(
            proposal, recipients, request, reminder=False
        )
        proposal_email.send_referral_email_notification(
            referral, recipients, request, reminder=False
        )
        proposal_email.send_referral_complete_email_notification(referral, request)
        proposal_email.send_amendment_email_notification(
            amendment_request, request, proposal
        )
        proposal_email.send_submit_email_notification(request, proposal)
        proposal_email.send_external_submit_email_notification(request, proposal)
        proposal_email.send_approver_decline_email_notification(
            reason, request, proposal
        )
        proposal_email.send_approver_approve_email_notification(request, proposal)
        proposal_email.send_proposal_decline_email_notification(
            proposal, request, proposal_decline
        )
        proposal_email.send_proposal_approver_sendback_email_notification(
            request, proposal
        )
        proposal_email.send_proposal_approval_email_notification(proposal, request)

        approval_email.send_approval_expire_email_notification(approval)
        approval_email.send_approval_cancel_email_notification(approval)
        approval_email.send_approval_suspend_email_notification(approval, request)
        approval_email.send_approval_surrender_email_notification(approval, request)
        approval_email.send_approval_renewal_email_notification(approval)
        approval_email.send_approval_reinstate_email_notification(approval, request)

        compliance_email.send_amendment_email_notification(
            amendment_request, request, compliance, is_test=True
        )
        compliance_email.send_reminder_email_notification(compliance, is_test=True)
        compliance_email.send_internal_reminder_email_notification(
            compliance, is_test=True
        )
        compliance_email.send_due_email_notification(compliance, is_test=True)
        compliance_email.send_internal_due_email_notification(compliance, is_test=True)
        compliance_email.send_compliance_accept_email_notification(
            compliance, request, is_test=True
        )
        compliance_email.send_external_submit_email_notification(
            request, compliance, is_test=True
        )
        compliance_email.send_submit_email_notification(
            request, compliance, is_test=True
        )

        booking_email.send_application_fee_invoice_tclass_email_notification(
            request, proposal, api, recipients, is_test=True
        )
        booking_email.send_application_fee_confirmation_tclass_email_notification(
            request, application_fee, api, recipients, is_test=True
        )
        booking_email.send_invoice_tclass_email_notification(
            request.user, booking, bi, recipients, is_test=True
        )
        booking_email.send_confirmation_tclass_email_notification(
            request.user, booking, bi, recipients, is_test=True
        )


def get_proposal_serializer_by_application_type(instance, context):
    """Return the appropriate serializer based on the application type of the proposal"""

    if instance.application_type.name == ApplicationType.TCLASS:
        logger.debug(f"Get serializer: {ApplicationType.TCLASS}")
        return InternalProposalSerializer(instance, context=context)
    elif instance.application_type.name == ApplicationType.FILMING:
        logger.debug(f"Get serializer: {ApplicationType.FILMING}")
        return InternalFilmingProposalSerializer(instance, context=context)
    elif instance.application_type.name == ApplicationType.EVENT:
        logger.debug(f"Get serializer: {ApplicationType.EVENT}")
        return InternalEventProposalSerializer(instance, context=context)
    else:
        logger.debug("Get default InternalProposalSerializer")
        return InternalProposalSerializer(instance, context=context)


def get_cached_application_types():
    application_types = cache.get(settings.CACHE_KEY_APPLICATION_TYPES)

    if application_types is None:
        application_types = ApplicationType.objects.filter(visible=True).values_list(
            "name", flat=True
        )

        cache.set(
            settings.CACHE_KEY_APPLICATION_TYPES,
            application_types,
            settings.CACHE_TIMEOUT_24_HOURS,
        )

    return application_types


def get_cached_proposal_submitters(view, queryset=None):
    if not queryset:
        queryset = view.get_queryset()
    cache_key = settings.CACHE_KEY_PROPOSAL_SUBMITTERS.format(view.__class__.__name__)
    submitters = cache.get(cache_key)

    if submitters is None:
        
        # 1) Collect unique submitter IDs from the proposals queryset
        submitter_ids = (
            queryset
            .filter(submitter__isnull=False)
            .distinct()
            .values_list("submitter_id", flat=True)
            
        )

        # 2) Fetch the EmailUser records for those IDs
        users_qs = (
            EmailUser.objects
            .filter(id__in=submitter_ids)
            .order_by("email")               # ordering to match original intent
            .values("email", "first_name", "last_name")
        )

        submitters = [
            {
                "email": u["email"],
                "search_term": f'{u["first_name"]} {u["last_name"]} ({u["email"]})',
            }
            for u in users_qs
        ]


        cache.set(
            cache_key,
            submitters,
            settings.CACHE_TIMEOUT_10_SECONDS,
        )

    return submitters

def get_proposal_processing_status():
    return [
                { "value": 'draft', "name": 'Draft' },
                { "value": 'with_assessor', "name": 'With Assessor' },
                { "value": 'on_hold', "name": 'On Hold' },
                { "value": 'with_qa_officer', "name": 'With QA Officer' },
                { "value": 'with_referral', "name": 'With Referral' },
                {"value": 'with_assessor_requirements',"name": 'With Assessor (Requirements)',},
                { "value": 'with_approver', "name": 'With Approver' },
                { "value": 'approved', "name": 'Approved' },
                { "value": 'declined', "name": 'Declined' },
                { "value": 'discarded', "name": 'Discarded' },
                { "value": 'awaiting_payment', "name": 'Awaiting Payment' },
            ]

def get_district_proposal_processing_status():
    return [
                { "value": 'approved', "name": 'Approved' },
                { "value": 'declined', "name": 'Declined' },
                { "value": 'with_approver', "name": 'With Approver' },
                { "value": 'with_assessor', "name": 'With Assessor' },
                {"value": 'with_assessor_requirements',"name": 'With Assessor (Requirements)',},   
            ]

def get_cached_proposal_processing_status(view, queryset=None):
    if not queryset:
        queryset = view.get_queryset()
    cache_key = settings.CACHE_KEY_PROPOSAL_PROCESSING_STATUS.format(
        view.__class__.__name__
    )
    processing_status = cache.get(cache_key)

    if processing_status is None:
        processing_status_qs = (
            queryset.filter(proposal__processing_status__isnull=False)
            .order_by("proposal__processing_status")
            .distinct("proposal__processing_status")
            .values_list("proposal__processing_status", flat=True)
        )
        processing_status = [
            dict(value=i, name="{}".format(" ".join(i.split("_")).capitalize()))
            for i in processing_status_qs
        ]

        cache.set(
            cache_key,
            processing_status,
            settings.CACHE_TIMEOUT_10_SECONDS,
        )

    return processing_status


def get_chained_list(
    context,
    searchWords,
    searchProposal,
    searchApproval,
    searchCompliance,
    is_internal=True,
):
    from commercialoperator.utils import (
        getChoiceFieldRegex,
    )
    from commercialoperator.components.approvals.models import Approval
    from commercialoperator.components.compliances.models import Compliance

    application_types = [
        ApplicationType.TCLASS,
        ApplicationType.EVENT,
        ApplicationType.FILMING,
    ]

    proposal_list = Proposal.objects.none()
    approval_list = Approval.objects.none()
    compliance_list = Compliance.objects.none()

    if is_internal and searchProposal:
        proposal_list = Proposal.objects.filter(
            application_type__name__in=application_types
        ).exclude(processing_status__in=["discarded", "draft"])
    if is_internal and searchApproval:
        approval_list = (
            Approval.objects.all()
            .order_by("lodgement_number", "-issue_date")
            .distinct("lodgement_number")
        )
    if is_internal and searchCompliance:
        compliance_list = Compliance.objects.all()

    if searchWords:
        matched_emailuser_ids = []
        matched_org_ids = []
        for search_word in searchWords:
            matched_emailuser_ids.extend(search_in_emailuser_fields(search_word))
            matched_org_ids.extend(search_organisation_properties(search_word, False))

        matched_emailuser_ids = list(set(matched_emailuser_ids))
        matched_org_ids = list(set(matched_org_ids))

        # convert the search words in to two regex values - one for text one for json values
        search_words_regex = "(?:" + "|".join(searchWords) + ")"
        filter_regex = (
            '.*".*":\s"(\\\\"|[^"])*' + search_words_regex + '(\\\\"|[^"])*".*'
        )

        # three searchable fields use choices: accreditation, film_type, and film_purpose
        # so we must convert the search phrase in to the search short word where applicable
        # accreditation
        accreditation_words = getChoiceFieldRegex(
            searchWords, ProposalAccreditation.ACCREDITATION_TYPE_CHOICES
        )
        # film type
        film_type_words = getChoiceFieldRegex(
            searchWords, ProposalFilmingActivity.FILM_TYPE_CHOICES
        )
        # film purpose
        film_purpose_words = getChoiceFieldRegex(
            searchWords, ProposalFilmingActivity.PURPOSE_CHOICES
        )

        # one particular search value is quite nested - it is faster to run these queries instead of the reverse
        activities = Activity.objects.filter(name__iregex=search_words_regex)
        pts_activities = ProposalTrailSectionActivity.objects.filter(
            activity__in=activities
        )
        sections = ProposalTrailSection.objects.filter(
            trail_activities__in=pts_activities
        )
        trails = ProposalTrail.objects.filter(sections__in=sections)

        paginator = context.paginator
        paginator.page_size = 10

        if searchProposal:
            # this below query run is equivalent to the search_words property, except that it retrieves the pertaining proposal records
            # there is a lot here but a lot of time is saved not having to iterate every record every time
            proposal_list = (
                proposal_list.filter(
                    (Q(lodgement_number__iregex=search_words_regex))
                    | Q(proxy_applicant_id__in=matched_emailuser_ids)
                    | Q(org_applicant_id__in=matched_org_ids)
                    | Q(submitter_id__in=matched_emailuser_ids)
                    | (
                        Q(application_type__name=ApplicationType.TCLASS)
                        & (Q(parks__park__name__iregex=search_words_regex))
                        | (Q(parks__activities__activity__in=activities))
                        | (Q(parks__zones__park_activities__activity__in=activities))
                        | (Q(trails__trail__name__iregex=search_words_regex))
                        | (Q(vehicles__rego__iregex=search_words_regex))
                        | (Q(vessels__spv_no__iregex=search_words_regex))
                        | (Q(other_details__other_comments__iregex=search_words_regex))
                        | (Q(other_details__mooring__iregex=search_words_regex))
                        | (
                            Q(
                                other_details__accreditations__accreditation_type__in=accreditation_words
                            )
                        )
                        | (Q(trails__in=trails))
                    )
                    | (
                        Q(application_type__name=ApplicationType.EVENT)
                        & (Q(events_parks__park__name__iregex=search_words_regex))
                        | (Q(events_parks__event_activities__iregex=search_words_regex))
                        | (Q(trails__trail__name__iregex=search_words_regex))
                        | (Q(vehicles__rego__iregex=search_words_regex))
                        | (Q(vessels__spv_no__iregex=search_words_regex))
                        | (Q(trails__in=trails))
                    )
                    | (
                        Q(application_type__name=ApplicationType.FILMING)
                        & (Q(filming_parks__park__name__iregex=search_words_regex))
                        | (Q(vehicles__rego__iregex=search_words_regex))
                        | (Q(vessels__spv_no__iregex=search_words_regex))
                        | (Q(filming_activity__film_type__in=film_type_words))
                        | (Q(filming_activity__film_purpose__in=film_purpose_words))
                    )
                )
                .distinct("id")
                .order_by("-id")
            )

        if searchApproval:
            approval_list = approval_list.filter(
                Q(lodgement_number__iregex=search_words_regex)
                | Q(proxy_applicant_id__in=matched_emailuser_ids)
                | Q(org_applicant_id__in=matched_org_ids)
                | Q(surrender_details__iregex=filter_regex)
                | Q(suspension_details__iregex=filter_regex)
                | Q(cancellation_details__iregex=search_words_regex)
            )

        if searchCompliance:
            compliance_list = compliance_list.filter(
                Q(lodgement_number__iregex=search_words_regex)
                | Q(approval__lodgement_number__iregex=search_words_regex)
                | Q(proposal__submitter_id__in=matched_emailuser_ids)
                | Q(proposal__proxy_applicant_id__in=matched_emailuser_ids)
                | Q(proposal__org_applicant_id__in=matched_org_ids)
                | Q(text__iregex=search_words_regex)
                | Q(requirement__free_requirement__iregex=search_words_regex)
                | Q(requirement__standard_requirement__text__iregex=search_words_regex)
            )

    return proposal_list, approval_list, compliance_list


def paginate_chained_list(context, request, chained_list, searchWords):
    from commercialoperator.utils import (
        search,
        search_approval,
        search_compliance,
        #     # getChoiceFieldRegex,
    )

    paginator = context.paginator
    paginator.page_size = 10

    return_list = []
    has_search_words = bool(searchWords)
    search_words_lower = [str(word).lower() for word in (searchWords or []) if word]

    def matches_search(value):
        candidate = str(value or "").lower()
        return any(word in candidate for word in search_words_lower)

    def serialize_proposal_entry(entry, text_value=""):
        pid = entry.id
        lodgement_number = entry.lodgement_number
        cache_key = settings.CACHE_KEY_PROPOSAL_KEYWORD_SEARCH.format(
            id=pid, lodgement_number=lodgement_number
        )
        res = cache.get(cache_key)

        if res is None:
            try:
                applicant = entry.applicant_obj
            except Proposal.DoesNotExist:
                applicant = None

            res = {
                "number": lodgement_number,
                "id": pid,
                "type": "Proposal",
                "applicant": applicant,
            }

            cache.set(
                cache_key,
                res,
                settings.CACHE_TIMEOUT_24_HOURS,
            )
        else:
            logger.info(
                "Search Keywords cache hit for proposal {}".format(res["number"])
            )

        res["text"] = text_value
        return res

    # Fast path: no keyword filtering requested. Paginate DB-backed queryset first.
    if not has_search_words:
        chained_list_paginated = paginator.paginate_queryset(chained_list, request, context)

        for entry in chained_list_paginated:
            if isinstance(entry, Proposal):
                return_list.append(serialize_proposal_entry(entry, ""))
            elif isinstance(entry, Approval):
                return_list.append(
                    {
                        "number": entry.lodgement_number,
                        "id": entry.id,
                        "type": "Approval",
                        "applicant": entry.applicant,
                        "text": "",
                    }
                )
            elif isinstance(entry, Compliance):
                return_list.append(
                    {
                        "number": entry.lodgement_number,
                        "id": entry.id,
                        "type": "Compliance",
                        "applicant": entry.proposal.applicant_obj,
                        "text": "",
                    }
                )
            else:
                raise ValueError(
                    f"Unknown entry type {type(entry)} in search results {entry}"
                )

        return return_list

    for entry in chained_list:
        if isinstance(entry, Proposal):
            final_results = ""

            if has_search_words:
                number_match = matches_search(entry.lodgement_number)
                proponent_match = matches_search(entry.applicant)
                search_results = []
                if entry.search_data:
                    search_results = search(entry.search_data, searchWords)

                if not number_match and not proponent_match and not len(search_results):
                    continue

                if len(search_results):
                    final_results = {}
                    for result in search_results:
                        for key, value in result.items():
                            final_results.update({"key": key, "value": value})

            return_list.append(serialize_proposal_entry(entry, final_results))

        elif isinstance(entry, Approval):
            try:
                results = search_approval(entry, searchWords)
                if not has_search_words and not results:
                    results = [
                        {
                            "number": entry.lodgement_number,
                            "id": entry.id,
                            "type": "Approval",
                            "applicant": entry.applicant,
                            "text": "",
                        }
                    ]
                if has_search_words and not results and matches_search(entry.lodgement_number):
                    results = [
                        {
                            "number": entry.lodgement_number,
                            "id": entry.id,
                            "type": "Approval",
                            "applicant": entry.applicant,
                            "text": "",
                        }
                    ]
                if has_search_words and not results and matches_search(entry.applicant):
                    results = [
                        {
                            "number": entry.lodgement_number,
                            "id": entry.id,
                            "type": "Approval",
                            "applicant": entry.applicant,
                            "text": "",
                        }
                    ]
                return_list.extend(results)
            except:
                pass
        elif isinstance(entry, Compliance):
            try:
                results = search_compliance(entry, searchWords)
                if not has_search_words and not results:
                    results = [
                        {
                            "number": entry.lodgement_number,
                            "id": entry.id,
                            "type": "Compliance",
                            "applicant": entry.proposal.applicant_obj,
                            "text": "",
                        }
                    ]
                compliance_number_match = matches_search(entry.lodgement_number)
                approval_number_match = matches_search(entry.approval.lodgement_number)
                proponent_match = matches_search(entry.proposal.applicant)
                if has_search_words and not results and (
                    compliance_number_match or approval_number_match or proponent_match
                ):
                    results = [
                        {
                            "number": entry.lodgement_number,
                            "id": entry.id,
                            "type": "Compliance",
                            "applicant": entry.proposal.applicant_obj,
                            "text": "",
                        }
                    ]
                return_list.extend(results)
            except:
                pass
        else:
            raise ValueError(
                f"Unknown entry type {type(entry)} in search results {entry}"
            )

    # Apply pagination after secondary filtering so page size and counts stay aligned.
    # DataTables paginator needs count hints on the view when paginating a plain list.
    setattr(context, "_datatables_filtered_count", len(return_list))
    if not hasattr(context, "_datatables_total_count"):
        setattr(context, "_datatables_total_count", len(return_list))
    return paginator.paginate_queryset(return_list, request, context)


def searchKeyWords(
    context,
    request,
    searchWords,
    searchProposal,
    searchApproval,
    searchCompliance,
    is_internal=True,
):
    proposal_list, approval_list, compliance_list = get_chained_list(
        context,
        searchWords,
        searchProposal,
        searchApproval,
        searchCompliance,
        is_internal,
    )
    chained_qs = QuerySetChain(proposal_list, approval_list, compliance_list)

    return paginate_chained_list(context, request, chained_qs, searchWords)
