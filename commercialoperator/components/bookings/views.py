import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic.base import TemplateView, View
from ledger_api_client.helpers import is_payment_admin
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from ledger_api_client.ledger_models import Invoice
from rest_framework import serializers, status, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from commercialoperator.components.bookings.confirmation_pdf import (
    create_confirmation_pdf_bytes,
)
from commercialoperator.components.bookings.context_processors import template_context
from commercialoperator.components.bookings.email import (
    send_application_fee_invoice_tclass_email_notification,
    send_compliance_fee_invoice_events_email_notification,
    send_confirmation_tclass_email_notification,
    send_invoice_tclass_email_notification,
)
from commercialoperator.components.bookings.models import (
    ApplicationFee,
    ApplicationFeeInvoice,
    Booking,
    BookingInvoice,
    ComplianceFee,
    ComplianceFeeInvoice,
    FilmingFee,
    FilmingFeeInvoice,
    ParkBooking,
)
from commercialoperator.components.bookings.monthly_confirmation_pdf import (
    create_monthly_confirmation_pdf_bytes,
)
from commercialoperator.components.bookings.utils import (
    checkout,
    checkout_existing_invoice,
    create_booking,
    create_bpay_invoice,
    create_compliance_fee_lines,
    create_fee_lines,
    create_lines,
    create_monthly_confirmation,
    create_other_invoice,
    delete_session_booking,
    get_invoice_pdf,
    get_invoice_properties,
    get_session_application_invoice,
    get_session_booking,
    get_session_compliance_invoice,
    get_session_filming_invoice,
    set_session_application_invoice,
    set_session_booking,
    set_session_compliance_invoice,
    set_session_filming_invoice,
)
from commercialoperator.components.compliances.models import Compliance
from commercialoperator.components.main.models import ApplicationType
from commercialoperator.components.organisations.models import (
    Organisation,
    OrganisationContact,
)
from commercialoperator.components.proposals.models import Proposal
from commercialoperator.components.proposals.utils import proposal_submit
from commercialoperator.helpers import is_in_organisation_contacts, is_internal

logger = logging.getLogger("payment_checkout")


class ApplicationFeeView(TemplateView):
    template_name = "commercialoperator/booking/success.html"

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs["proposal_pk"])

    def post(self, request, *args, **kwargs):

        try:
            proposal = self.get_object()

            user = request.user
            user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
            if not (
                is_internal(self.request)
                or proposal.org_applicant_id in user_orgs
                or proposal.submitter == user
            ):
                raise PermissionDenied

            if request.user and isinstance(request.user, EmailUser):
                if not proposal.submitter:
                    proposal.submitter = (
                        request.user
                    )  # NOTE: submitter should already be set
                    proposal.save()
                # Same org, different submitter
                if (
                    proposal.org_applicant
                    and OrganisationContact.objects.filter(
                        organisation=proposal.org_applicant, email=request.user.email
                    ).exists()
                ):
                    proposal.submitter = request.user
                    proposal.save()

            application_fee = ApplicationFee.objects.create(
                proposal=proposal,
                created_by=request.user,
                payment_type=ApplicationFee.PAYMENT_TYPE_TEMPORARY,
            )

            with transaction.atomic():
                lines = create_fee_lines(proposal)

                set_session_application_invoice(request.session, application_fee)
                return_url = request.build_absolute_uri(
                    reverse(
                        "fee_success", kwargs={"reference": proposal.lodgement_number}
                    )
                )
                return_preload_url = settings.COMMERCIALOPERATOR_EXTERNAL_URL + reverse(
                    "fee_success_preload",
                    kwargs={"reference": proposal.lodgement_number},
                )
                checkout_response = checkout(
                    request,
                    proposal,
                    lines,
                    return_url,
                    return_preload_url,
                    invoice_text="Application Fee",
                    reference=proposal.lodgement_number,
                )

                # Set session variables
                request.session["payment_pk"] = proposal.pk
                request.session["payment_model"] = "proposal"

                logger.info(
                    "{} built payment line item {} for Application Fee and handing over to payment gateway".format(
                        f"User {proposal.submitter.get_full_name()} with id {proposal.submitter.id}",
                        proposal.id,
                    )
                )
                return checkout_response

        except Exception as e:
            logger.error(f"Error Creating Application Fee: {e}")
            if application_fee:
                application_fee.delete()
            raise


class ComplianceFeeView(TemplateView):
    template_name = "commercialoperator/booking/success.html"

    def get_object(self):
        return get_object_or_404(Compliance, id=self.kwargs["compliance_pk"])

    def post(self, request, *args, **kwargs):

        compliance = self.get_object()

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or compliance.proposal.org_applicant in user_orgs
            or compliance.proposal.submitter == user
        ):
            raise PermissionDenied

        compliance_fee = ComplianceFee.objects.create(
            compliance=compliance,
            created_by=request.user,
            payment_type=ComplianceFee.PAYMENT_TYPE_TEMPORARY,
        )

        # NOTE: files have to be uploaded prior to payment
        # TODO: file upload does not appear to work - investigate (here and in the standard submit)
        # TODO: consider file upload as a separate process to submission so users don't have to upload every submit attempt
        if request.FILES:
            for f in request.FILES:
                document = compliance.documents.create(name=str(request.FILES[f]))
                document._file = request.FILES[f]
                document.save()

        try:
            with transaction.atomic():
                set_session_compliance_invoice(request.session, compliance_fee)
                lines = create_compliance_fee_lines(compliance)
                return_url = request.build_absolute_uri(
                    reverse(
                        "compliance_fee_success",
                        kwargs={"reference": compliance.lodgement_number},
                    )
                )
                return_preload_url = settings.COMMERCIALOPERATOR_EXTERNAL_URL + reverse(
                    "compliance_success_preload",
                    kwargs={"reference": compliance.lodgement_number},
                )
                checkout_response = checkout(
                    request,
                    compliance.proposal,
                    lines,
                    return_url,
                    return_preload_url,
                    invoice_text="Per participant licence charge",
                    reference=compliance.lodgement_number,
                )

                # Set session variables
                # TODO rework to use its own model (if necessary)
                request.session["payment_pk"] = compliance.proposal.pk
                request.session["payment_model"] = "proposal"

                logger.info(
                    "{} built payment line item {} for Compliance Fee and handing over to payment gateway".format(
                        f"User {compliance.proposal.submitter.get_full_name()} with id {compliance.proposal.submitter.id}",
                        compliance.id,
                    )
                )
                return checkout_response

        except Exception as e:
            logger.error(f"Error Creating Compliance Fee: {e}")
            if compliance_fee:
                compliance_fee.delete()
            raise


class FilmingFeeView(TemplateView):
    template_name = "commercialoperator/booking/success.html"

    def get_object(self):
        return get_object_or_404(Proposal, id=self.kwargs["proposal_pk"])

    @transaction.atomic
    def get(self, request, *args, **kwargs):
        proposal = self.get_object()

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or proposal.org_applicant in user_orgs
            or proposal.submitter == user
        ):
            raise PermissionDenied

        filming_fee = proposal.filming_fees.order_by("-id").first()
        inv_ref = (
            filming_fee.filming_fee_invoices.order_by("-id").first().invoice_reference
        )

        try:
            set_session_filming_invoice(request.session, filming_fee)
            invoice = Invoice.objects.get(reference=inv_ref)

            checkout_response = checkout_existing_invoice(
                request,
                proposal.lodgement_number,
                invoice,
                return_url_ns="filming_fee_success",
            )

            logger.info(
                "{} built payment line item {} for Proposal Fee and handing over to payment gateway".format(
                    f"User {proposal.submitter.get_full_name()} with id {proposal.submitter.id}",
                    proposal.id,
                )
            )

            # Set session variables
            request.session["payment_pk"] = proposal.pk
            request.session["payment_model"] = "proposal"

            return checkout_response

        except Exception as e:
            logger.error(f"Error Creating Proposal Fee: {e}")
            if filming_fee:
                filming_fee.delete()
            raise


# TODO (may not be needed, in which case remove)
class DeferredInvoicingPreviewView(View):
    template_name = "commercialoperator/booking/preview_deferred.html"

    def post(self, request, *args, **kwargs):
        proposal = get_object_or_404(Proposal, id=kwargs["proposal_pk"])
        user = request.user

        # Permission check
        is_user_org = (
            proposal.org_applicant_id is not None
            and user.commercialoperator_organisations.filter(
                id=proposal.org_applicant_id
            ).exists()
        )
        if not (is_internal(request) or is_user_org or proposal.submitter == user):
            raise PermissionDenied

        # Check deferred invoicing eligibility
        org = proposal.org_applicant
        is_allowed = isinstance(org, Organisation) and (
            org.monthly_invoicing_allowed
            or org.bpay_allowed
            or (settings.OTHER_PAYMENT_ALLOWED and is_payment_admin(user))
        )

        if not is_allowed:
            logger.warning(
                f"Deferred invoicing not allowed for Proposal {proposal.id} (User: {user.id})"
            )
            raise PermissionDenied(
                "Deferred invoicing is not permitted for this organisation."
            )

        try:
            lines = create_lines(request)
            payment_details = request.POST.get("payment")

            logger.info(
                "Show Park Bookings Preview for BPAY/Other/monthly invoicing for "
                f"User {proposal.submitter.get_full_name()} (ID: {proposal.submitter.id})"
            )

            context = {
                **template_context(request),
                "lines": lines,
                "line_details": payment_details,
                "proposal_id": proposal.id,
                "submitter": getattr(proposal, "applicant", proposal.submitter),
                "payment_method": request.GET.get("method"),
            }
            return render(request, self.template_name, context)

        except Exception:
            logger.exception(
                f"Error creating booking preview for Proposal {proposal.id}"
            )
            return HttpResponseBadRequest("Unable to generate booking preview.")


# TODO replace below with appropriate payment functionality (may not be needed, in which case remove)
class DeferredInvoicingView(View):
    template_name = "commercialoperator/booking/success.html"

    def post(self, request, *args, **kwargs):
        proposal = get_object_or_404(Proposal, id=kwargs["proposal_pk"])
        user = request.user
        payment_method = request.POST.get("method")

        # 1. Base permission check
        is_user_org = (
            proposal.org_applicant_id is not None
            and user.commercialoperator_organisations.filter(
                id=proposal.org_applicant_id
            ).exists()
        )
        if not (is_internal(request) or is_user_org or proposal.submitter == user):
            raise PermissionDenied

        org = proposal.org_applicant
        if not isinstance(org, Organisation):
            logger.error(
                f"Proposal {proposal.id} applicant is not a valid Organisation."
            )
            raise PermissionDenied("A valid organisation applicant is required.")

        # 2. Validate 'other' payment permissions BEFORE performing DB writes
        if payment_method == "other" and not is_payment_admin(user):
            raise PermissionDenied(
                "You do not have permission to use this payment method."
            )

        # Determine booking type
        if org.bpay_allowed and payment_method == "bpay":
            booking_type = Booking.BOOKING_TYPE_INTERNET
        elif org.monthly_invoicing_allowed and payment_method == "monthly_invoicing":
            booking_type = Booking.BOOKING_TYPE_MONTHLY_INVOICING
        else:
            booking_type = Booking.BOOKING_TYPE_RECEPTION

        submitter = getattr(proposal, "applicant", proposal.submitter)
        booking = None
        invoice_reference = None

        try:
            booking = create_booking(request, proposal, booking_type=booking_type)

            if booking:
                if payment_method == "bpay":
                    create_bpay_invoice(submitter, booking)
                    invoice_reference = booking.invoice.reference
                elif payment_method == "other":
                    create_other_invoice(submitter, booking)
                    invoice_reference = booking.invoice.reference
                elif payment_method == "monthly_invoicing":
                    create_monthly_confirmation(submitter, booking)

            logger.info(
                f"User {proposal.submitter.get_full_name()} (ID: {proposal.submitter.id}) "
                f"created booking {getattr(booking, 'id', None)} with method '{payment_method}' "
                f"for Proposal ID {proposal.id}"
            )

            # Redirect if payment method is "other"
            if payment_method == "other":
                redirect_url = reverse("payments:invoice-payment")
                return HttpResponseRedirect(
                    f"{redirect_url}?invoice={invoice_reference}"
                )

            context = {
                **template_context(request),
                "booking": booking,
                "booking_id": getattr(booking, "id", None),
                "submitter": submitter,
                "monthly_invoicing": (payment_method == "monthly_invoicing"),
                "invoice_reference": invoice_reference,
            }
            return render(request, self.template_name, context)

        except Exception:
            logger.exception(f"Error creating booking for Proposal ID {proposal.id}")
            if booking and getattr(booking, "id", None):
                booking.delete()
            raise


# TODO: determine if non-cc payments are still required - handle as needed with alternative payment approaches (if required)
class MakePaymentView(TemplateView):
    """View to handle Park Entry Fees:Make Payment"""

    template_name = "commercialoperator/booking/success.html"

    def post(self, request, *args, **kwargs):

        proposal_id = int(kwargs["proposal_pk"])
        proposal = Proposal.objects.get(id=proposal_id)

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or proposal.org_applicant in user_orgs
            or proposal.submitter == user
        ):
            raise PermissionDenied

        booking = None

        try:
            booking = create_booking(
                request, proposal, booking_type=Booking.BOOKING_TYPE_TEMPORARY
            )

            unique_sets = {frozenset(d.items()) for d in booking.as_line_items}

            # check for duplicate bookings/lines
            unique_lines = [dict(s) for s in unique_sets]

            if len(booking.as_line_items) != len(unique_lines):
                logger.warning("Booking contains dupicate rows.")

            with transaction.atomic():
                set_session_booking(request.session, booking)
                return_url = request.build_absolute_uri(
                    reverse(
                        "public_booking_success",
                        kwargs={"reference": proposal.lodgement_number},
                    )
                )
                return_preload_url = settings.COMMERCIALOPERATOR_EXTERNAL_URL + reverse(
                    "public_booking_success_preload",
                    kwargs={"reference": proposal.lodgement_number},
                )
                checkout_response = checkout(
                    request,
                    proposal,
                    booking.as_line_items,
                    return_url,
                    return_preload_url,
                    invoice_text="Payment Invoice",
                    reference=proposal.lodgement_number,
                )

                # Set session variables
                # TODO use booking pk and model instead
                request.session["payment_pk"] = proposal.pk
                request.session["payment_model"] = "proposal"

                logger.info(
                    "{} built payment line items {} for Park Bookings and handing over to payment gateway".format(
                        f"User {proposal.submitter.get_full_name()} with id {proposal.submitter.id}",
                        proposal.id,
                    )
                )
                return checkout_response

        except Exception as e:
            logger.error(f"Error Creating booking: {e}")
            raise


class ComplianceFeeSuccessViewPreload(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, reference, format=None):
        logger.debug("ComplianceFeeSuccessViewPreload")

        invoice_ref = request.GET.get("invoice")

        try:
            compliance = Compliance.objects.get(lodgement_number=reference)
            logger.debug(f"Compliance: {compliance}")
        except Exception:
            logger.exception()
            return redirect("home")

        # use the latest Fee record
        compliance_fee = (
            ComplianceFee.objects.filter(compliance=compliance)
            .order_by("created")
            .last()
        )

        _, _ = ComplianceFeeInvoice.objects.get_or_create(
            compliance_fee=compliance_fee, invoice_reference=invoice_ref
        )

        if compliance_fee.payment_type == ComplianceFee.PAYMENT_TYPE_TEMPORARY:
            compliance_fee.payment_type = ComplianceFee.PAYMENT_TYPE_INTERNET
            compliance_fee.expiry_time = None
            success = False
            try:
                inv = Invoice.objects.get(reference=invoice_ref)
                invoice_properties = get_invoice_properties(inv.id)
                payment_status = invoice_properties.get("invoice", {}).get(
                    "payment_status"
                )

                if payment_status == "paid" or payment_status == "over_paid":
                    compliance.submit()
                    compliance.fee_invoice_reference = invoice_ref
                    compliance.save()
                    success = False
                else:
                    logger.error(f"Invoice payment status is {payment_status}")
                    raise serializers.ValidationError(
                        f"Invoice payment status is {payment_status}"
                    )

            except Exception:
                msg = "Fee success preload failed"
                logger.exception(msg)
                raise serializers.ValidationError(msg)

            if success:
                compliance_fee.save()
                try:
                    send_compliance_fee_invoice_events_email_notification(  # TODO fix this
                        request,
                        compliance,
                        inv,
                        recipients=[compliance.proposal.submitter.email],
                    )
                except Exception as e:
                    # log the error but do not invalidate the payment and subsequent compliance submission
                    logger.exception(
                        "Unable to send compliance fee invoice email notification",
                        exc_info=e,
                    )

        return Response(status=status.HTTP_200_OK)


class ComplianceFeeSuccessView(TemplateView):
    template_name = "commercialoperator/booking/success_compliance_fee.html"

    def get(self, request, *args, **kwargs):
        logger.debug("ComplianceFeeSuccessView")
        lodgement_number = kwargs.get("reference")

        try:
            compliance = Compliance.objects.get(lodgement_number=lodgement_number)
        except Compliance.DoesNotExist:
            raise serializers.ValidationError("Compliance does not exist")
        except Compliance.MultipleObjectsReturned:
            raise serializers.ValidationError("Multiple Compliances returned")

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or compliance.proposal.org_applicant in user_orgs
            or compliance.proposal.submitter == user
        ):
            raise PermissionDenied

        compliance_fee = get_session_compliance_invoice(request.session)
        fee_inv = compliance_fee.compliance_fee_invoices.order_by("-id").first()
        invoice_ref = fee_inv.invoice_reference

        try:
            inv = Invoice.objects.get(reference=invoice_ref)
        except Invoice.DoesNotExist:
            inv = None

        context = {
            "proposal": compliance.proposal,
            "submitter": compliance.submitter,
            "fee_invoice": inv,
        }
        return render(request, self.template_name, context)


class FilmingFeeSuccessViewPreload(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, reference, format=None):
        logger.debug("FilmFeeSuccessViewPreload")

        invoice_ref = request.GET.get("invoice")

        try:
            proposal = Proposal.objects.get(lodgement_number=reference)
            logger.debug(f"proposal: {proposal}")
        except Exception:
            logger.exception()
            return redirect("home")

        invoice = FilmingFeeInvoice.objects.filter(invoice_reference=invoice_ref).last()

        if not invoice:
            raise serializers.ValidationError("Filming Fee not found")

        filming_fee = invoice.filming_fee

        if filming_fee.proposal != proposal:
            raise serializers.ValidationError(
                "Filming Fee Proposal does not match provided lodgement number"
            )

        if filming_fee.payment_type == FilmingFee.PAYMENT_TYPE_TEMPORARY:
            filming_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
            filming_fee.expiry_time = None
            success = False
            try:
                inv = Invoice.objects.get(reference=invoice_ref)
                invoice_properties = get_invoice_properties(inv.id)
                payment_status = invoice_properties.get("invoice", {}).get(
                    "payment_status"
                )
                if proposal and payment_status in ["paid", "over_paid"]:
                    proposal.fee_invoice_reference = invoice_ref
                    proposal.save()
                    proposal.final_approval()
                    proposal.reset_application_discount(
                        proposal.submitter
                    )  # TODO verify using submitter is ok
                else:
                    logger.error(f"Invoice payment status is {inv.payment_status}")
                    raise serializers.ValidationError(
                        f"Invoice payment status is {inv.payment_status}"
                    )
            except Exception:
                msg = "Fee success preload failed"
                logger.exception(msg)
                raise serializers.ValidationError(msg)

            if success:
                filming_fee.save()

        return Response(status=status.HTTP_200_OK)


class FilmingFeeSuccessView(TemplateView):
    template_name = "commercialoperator/booking/success_fee.html"

    def get(self, request, *args, **kwargs):
        logger.debug("FilmingFeeSuccessView")
        lodgement_number = kwargs.get("reference")

        try:
            proposal = Proposal.objects.get(lodgement_number=lodgement_number)
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("Proposal does not exist")

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or proposal.org_applicant in user_orgs
            or proposal.submitter == user
        ):
            raise PermissionDenied

        filming_fee = get_session_filming_invoice(request.session)
        fee_inv = filming_fee.filming_fee_invoices.order_by("-id").first()
        invoice_ref = fee_inv.invoice_reference

        # TODO review all instances of fee success "submitter" being set -
        # check the template and check if the information is accurate RE emails sent and to where
        applicant = getattr(proposal, "applicant_obj", None)
        submitter = None

        if applicant and getattr(applicant, "email", None):
            submitter = applicant.email
        elif proposal and getattr(proposal, "submitter", None):
            submitter = proposal.submitter.email

        try:
            inv = Invoice.objects.get(reference=invoice_ref)
        except Invoice.DoesNotExist:
            logger.warning(
                f"Invoice instance with reference '{invoice_ref}' does not exist"
            )
            inv = None

        context = {"proposal": proposal, "submitter": submitter, "fee_invoice": inv}
        return render(request, self.template_name, context)


class ApplicationFeeSuccessViewPreload(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, reference, format=None):
        logger.debug("ApplicationFeeSuccessViewPreload")

        invoice_ref = request.GET.get("invoice")

        try:
            proposal = Proposal.objects.get(lodgement_number=reference)
            logger.debug(f"proposal:{proposal}")
        except Exception:
            logger.exception()
            return redirect("home")

        # use the latest Fee record
        proposal_fee = (
            ApplicationFee.objects.filter(proposal=proposal).order_by("created").last()
        )

        _, _ = ApplicationFeeInvoice.objects.get_or_create(
            application_fee=proposal_fee, invoice_reference=invoice_ref
        )

        if proposal_fee.payment_type == ApplicationFee.PAYMENT_TYPE_TEMPORARY:
            proposal_fee.payment_type = ApplicationFee.PAYMENT_TYPE_INTERNET
            proposal_fee.expiry_time = None
            success = False
            try:
                inv = Invoice.objects.get(reference=invoice_ref)
                invoice_properties = get_invoice_properties(inv.id)
                payment_status = invoice_properties.get("invoice", {}).get(
                    "payment_status"
                )

                if payment_status == "paid" or payment_status == "over_paid":
                    proposal = proposal_submit(proposal)
                    proposal.fee_invoice_reference = invoice_ref
                    proposal.save()
                    proposal.reset_application_discount(proposal.submitter)
                    success = True
                else:
                    logger.error(f"Invoice payment status is {payment_status}")
                    raise serializers.ValidationError(
                        f"Invoice payment status is {payment_status}"
                    )

            except Exception:
                msg = "Fee success preload failed"
                logger.exception(msg)
                raise serializers.ValidationError(msg)

            if success:
                proposal_fee.save()
                applicant = proposal.applicant_obj
                try:
                    recipient = Organisation.objects.get(id=applicant.id).email
                except Organisation.DoesNotExist:
                    recipient = proposal.submitter.email

                try:
                    # NOTE: request=None works fine with this email function
                    send_application_fee_invoice_tclass_email_notification(
                        request, proposal, inv, recipients=[recipient]
                    )
                except Exception as e:
                    # log the error but do not invalidate the payment and subsequent compliance submission
                    logger.exception(
                        "Unable to send compliance fee invoice email notification",
                        exc_info=e,  # 2. Explicitly pass it to the logger
                    )

        return Response(status=status.HTTP_200_OK)


class ApplicationFeeSuccessView(TemplateView):
    template_name = "commercialoperator/booking/success_fee.html"

    def get(self, request, *args, **kwargs):
        logger.debug("ApplicationFeeSuccessView")
        lodgement_number = kwargs.get("reference")

        try:
            proposal = Proposal.objects.get(lodgement_number=lodgement_number)
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("Proposal does not exist")

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or proposal.org_applicant in user_orgs
            or proposal.submitter == user
        ):
            raise PermissionDenied

        application_fee = get_session_application_invoice(request.session)

        fee_inv = application_fee.application_fee_invoices.order_by("-id").first()
        invoice_ref = fee_inv.invoice_reference

        # TODO review all instances of fee success "submitter" being set -
        # check the template and check if the information is accurate RE emails sent and to where
        applicant = getattr(proposal, "applicant_obj", None)
        submitter = None

        if applicant and getattr(applicant, "email", None):
            submitter = applicant.email
        elif proposal and getattr(proposal, "submitter", None):
            submitter = proposal.submitter.email

        try:
            inv = Invoice.objects.get(reference=invoice_ref)
        except Invoice.DoesNotExist:
            logger.warning(
                f"Invoice instance with reference '{invoice_ref}' does not exist"
            )
            inv = None

        context = {"proposal": proposal, "submitter": submitter, "fee_invoice": inv}
        return render(request, self.template_name, context)


class BookingSuccessViewPreload(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, reference, format=None):
        logger.debug("BookingSuccessViewPreload")

        invoice_ref = request.GET.get("invoice")

        try:
            proposal = Proposal.objects.get(lodgement_number=reference)
            logger.debug(f"proposal: {proposal}")
        except Exception:
            logger.exception()
            return redirect("home")

        # use the latest Fee record
        booking = Booking.objects.filter(proposal=proposal).order_by("created").last()

        _, created = BookingInvoice.objects.get_or_create(
            booking=booking,
            invoice_reference=invoice_ref,
            payment_method=Invoice.PAYMENT_METHOD_CC,  # if we are here, it was paid by credit_card
        )

        if created:
            submitter = getattr(proposal, "submitter", None)

            if submitter:
                user_info = f"User {submitter.get_full_name()} with id {submitter.id}"
            else:
                user_info = "System/Unknown User"

            booking_id = getattr(booking, "id", "Unknown")

            logger.info(
                f"{user_info} Created Park Bookings Invoice {invoice_ref} for Booking ID {booking_id}"
            )

        if booking.booking_type == Booking.BOOKING_TYPE_TEMPORARY:
            booking.booking_type = Booking.BOOKING_TYPE_INTERNET
            booking.expiry_time = None
            success = False
            try:
                inv = Invoice.objects.get(reference=invoice_ref)
                invoice_properties = get_invoice_properties(inv.id)
                payment_status = invoice_properties.get("invoice", {}).get(
                    "payment_status"
                )

                if payment_status == "paid" or payment_status == "over_paid":
                    success = True
                else:
                    logger.error(f"Invoice payment status is {payment_status}")
                    raise serializers.ValidationError(
                        f"Invoice payment status is {payment_status}"
                    )

            except Exception:
                msg = "Fee success preload failed"
                logger.exception(msg)
                raise serializers.ValidationError("Fee success preload failed")

            if success:
                booking.save()

                applicant_email = getattr(
                    getattr(proposal, "applicant", None), "email", None
                )
                submitter_email = getattr(
                    getattr(proposal, "submitter", None), "email", None
                )

                recipients = []
                if applicant_email:
                    recipients.append(applicant_email)
                elif submitter_email:
                    recipients.append(submitter_email)

                if recipients:
                    submitter_user = getattr(proposal, "submitter", None)

                    send_invoice_tclass_email_notification(
                        submitter_user, booking, inv, recipients=recipients
                    )
                    send_confirmation_tclass_email_notification(
                        submitter_user, booking, inv, recipients=recipients
                    )
                else:
                    # Critical safety log: Always log if a customer didn't get their invoice..
                    logger.error(
                        f"Booking {booking.id} saved successfully, but no recipient email "
                        f"could be found on proposal {proposal.id}. Notifications were NOT sent."
                    )

        return Response(status=status.HTTP_200_OK)


class BookingSuccessView(TemplateView):
    template_name = "commercialoperator/booking/success.html"

    def get(self, request, *args, **kwargs):
        logger.debug("BookingSuccessView")
        lodgement_number = kwargs.get("reference")

        try:
            proposal = Proposal.objects.get(lodgement_number=lodgement_number)
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("Proposal does not exist")

        user = request.user

        user_orgs = [org.id for org in user.commercialoperator_organisations.all()]
        if not (
            is_internal(self.request)
            or proposal.org_applicant in user_orgs
            or proposal.submitter == user
        ):
            raise PermissionDenied

        booking = Booking.objects.filter(proposal=proposal).order_by("created").last()
        session_booking = get_session_booking(request.session)

        if booking != session_booking:
            logger.warning("Latest booking record and booking in session do not match")

        # TODO review all instances of fee success "submitter" being set -
        # check the template and check if the information is accurate RE emails sent and to where
        applicant = getattr(proposal, "applicant_obj", None)
        submitter = None

        if applicant and getattr(applicant, "email", None):
            submitter = applicant.email
        elif proposal and getattr(proposal, "submitter", None):
            submitter = proposal.submitter.email

        fee_inv = booking.invoices.order_by("-id").first()
        invoice_ref = fee_inv.invoice_reference

        try:
            inv = Invoice.objects.get(reference=invoice_ref)
        except Invoice.DoesNotExist:
            inv = None

        context = {
            "booking_id": booking.id,
            "submitter": submitter,
            "payer": request.user,
            "invoice_reference": inv.reference if inv else None,
        }
        return render(request, self.template_name, context)


class InvoicePDFView(View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])
        bi = BookingInvoice.objects.filter(invoice_reference=invoice.reference).last()

        if bi:
            proposal = bi.booking.proposal
        else:
            proposal = Proposal.objects.get(fee_invoice_reference=invoice.reference)

        organisation = proposal.org_applicant

        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")

            invoice_pdf = get_invoice_pdf(invoice.reference)

            if invoice_pdf.status_code == status.HTTP_200_OK or is_payment_admin(
                request.user
            ):
                response.write(invoice_pdf.content)
                return response

        raise PermissionDenied

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs["reference"])

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class InvoiceFilmingFeePDFView(View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])
        proposal = Proposal.objects.get(fee_invoice_reference=invoice.reference)

        organisation = proposal.org_applicant
        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")
            invoice_pdf = get_invoice_pdf(invoice.reference)

            if invoice_pdf.status_code == status.HTTP_200_OK:
                response.write(invoice_pdf.content)
                return response
            else:
                logger.error(
                    f"Error getting PDF for invoice {invoice.reference}: {invoice_pdf.reason}"
                )

        raise PermissionDenied

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs["reference"])

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class InvoiceCompliancePDFView(View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])
        cfi = ComplianceFeeInvoice.objects.filter(
            invoice_reference=invoice.reference
        ).last()

        compliance = cfi.compliance_fee.compliance

        organisation = (
            compliance.proposal.org_applicant if compliance.proposal else None
        )
        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")

            invoice_pdf = get_invoice_pdf(invoice.reference)
            if invoice_pdf.status_code == status.HTTP_200_OK:
                response.write(invoice_pdf.content)
                return response
            else:
                logger.error(
                    f"Error getting PDF for invoice {invoice.reference}: {invoice_pdf.reason}"
                )
            return response
        raise PermissionDenied

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs["reference"])

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class ConfirmationPDFView(View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])
        bi = BookingInvoice.objects.filter(invoice_reference=invoice.reference).last()
        organisation = bi.booking.proposal.org_applicant

        if self.check_owner(organisation):
            # GST ignored here because GST amount is not included on the confirmation PDF
            response = HttpResponse(content_type="application/pdf")
            response.write(
                create_confirmation_pdf_bytes("confirmation.pdf", invoice, bi.booking)
            )
            return response
        raise PermissionDenied

    def get_object(self):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])
        return invoice

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class MonthlyConfirmationPDFBookingView(View):
    """for the Visitor Admissions Payment Dashboard - View by Booking (payments_dashboard.vue)"""

    def get(self, request, *args, **kwargs):
        booking = get_object_or_404(Booking, id=self.kwargs["id"])
        organisation = booking.proposal.org_applicant

        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")
            response.write(
                create_monthly_confirmation_pdf_bytes(
                    "monthly_confirmation.pdf", booking
                )
            )
            return response
        raise PermissionDenied

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class MonthlyConfirmationPDFParkBookingView(View):
    """for the Visitor Admissions Payment Dashboard - View by ParkBooking (parkbookings_dashboard.vue)"""

    def get(self, request, *args, **kwargs):
        park_booking = get_object_or_404(ParkBooking, id=self.kwargs["id"])
        booking = park_booking.booking
        organisation = (
            booking.proposal.org_applicant.organisation.organisation_set.all()[0]
        )

        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")
            response.write(
                create_monthly_confirmation_pdf_bytes(
                    "monthly_confirmation.pdf", booking
                )
            )
            return response
        raise PermissionDenied

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class AwaitingPaymentInvoicePDFView(View):
    def get(self, request, *args, **kwargs):
        proposal = get_object_or_404(Proposal, id=self.kwargs["id"])
        organisation = proposal.org_applicant

        if self.check_owner(organisation):
            response = HttpResponse(content_type="application/pdf")

            if proposal.application_type.name == ApplicationType.FILMING:
                invoice = Invoice.objects.get(
                    reference=proposal.filming_fee_invoice_reference
                )
            else:
                invoice = proposal.invoice

            if not invoice:
                raise Http404("Invoice not found")

            invoice_pdf = get_invoice_pdf(invoice.reference)

            if invoice_pdf.status_code == status.HTTP_200_OK:
                response.write(invoice_pdf.content)
                return response

        raise PermissionDenied

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class InvoicePaymentView(View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs["reference"])

        if is_payment_admin(request.user):
            ledger_invoice_url = urljoin(
                settings.LEDGER_UI_URL,
                f"ledger/payments/oracle/payments?invoice_no={invoice.reference}",
            )
            return HttpResponseRedirect(ledger_invoice_url)

        raise PermissionDenied

    def get_object(self):
        return get_object_or_404(Invoice, reference=self.kwargs["reference"])

    def check_owner(self, organisation):
        return (
            is_in_organisation_contacts(self.request, organisation)
            or is_internal(self.request)
            or self.request.user.is_superuser
        )


class SessionAbortRedirectView(TemplateView):
    template_name = "commercialoperator/booking/abort_session.html"

    def get(self, request, *args, **kwargs):
        booking = None
        context = None
        action = request.GET.get("action", None)

        booking = get_session_booking(request.session)

        if booking and getattr(booking, "booking_type", None) == 3:
            booking.delete()

        delete_session_booking(request.session)

        if action == "quit":
            # if the user wants to quit, we redirect to the home page
            return HttpResponseRedirect(reverse("home"))

        context = template_context(self.request)
        return render(request, self.template_name, context)
