import json
import logging
from datetime import date, datetime
from decimal import Decimal

import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from ledger_api_client.ledger_models import Invoice
from ledger_api_client.utils import (
    create_basket_session,
    create_checkout_session,
    generate_payment_session,
)
from rest_framework import status
from taggit import serializers

from commercialoperator.components.bookings.email import (
    send_confirmation_tclass_email_notification,
    send_invoice_tclass_email_notification,
    send_monthly_confirmation_tclass_email_notification,
    send_monthly_invoice_tclass_email_notification,
)
from commercialoperator.components.bookings.models import (
    ApplicationFee,
    Booking,
    BookingInvoice,
    ComplianceFee,
    FilmingFee,
    ParkBooking,
)
from commercialoperator.components.main.models import ApplicationType, Park
from commercialoperator.components.organisations.models import Organisation
from commercialoperator.components.proposals.models import Proposal, ProposalUserAction
from commercialoperator.components.segregation.classes import DecimalEncoder
from commercialoperator.components.segregation.utils import (
    createCustomBasket,
    oracle_parser,
)

logger = logging.getLogger("payment_checkout")


def create_booking(request, proposal, booking_type=Booking.BOOKING_TYPE_TEMPORARY):
    """Create the ledger lines - line items for invoice sent to payment system"""

    if (
        booking_type == Booking.BOOKING_TYPE_MONTHLY_INVOICING
        and proposal.org_applicant
        and proposal.org_applicant.monthly_invoicing_allowed
    ):
        booking, _ = Booking.objects.get_or_create(
            invoices__isnull=True,
            proposal_id=proposal.id,
            booking_type=booking_type,
            created__month=timezone.now().month,
            defaults={
                "created_by": request.user,
                "created": timezone.now(),
            },
        )
        lines = json.loads(request.POST["line_details"])["tbody"]

    elif (
        booking_type == Booking.BOOKING_TYPE_INTERNET
        and proposal.org_applicant
        and proposal.org_applicant.bpay_allowed
    ) or (booking_type == Booking.BOOKING_TYPE_RECEPTION):
        booking = Booking.objects.create(
            proposal_id=proposal.id, created_by=request.user, booking_type=booking_type
        )
        lines = json.loads(request.POST["line_details"])["tbody"]

    else:
        booking = Booking.objects.create(
            proposal_id=proposal.id, created_by=request.user, booking_type=booking_type
        )

        payment_serialized = request.POST.getlist("payment", [""])[0]
        lines = json.loads(payment_serialized).get("tbody", [])

    for row in lines:
        park_id = row[0]  # ["value"]
        arrival = row[1]
        same_tour_group = row[2] == True
        no_adults = int(row[3]) if row[3] else 0
        no_children = int(row[4]) if row[4] else 0
        no_free_of_charge = int(row[5]) if row[5] else 0
        park = Park.objects.get(id=park_id)

        # same tour group visitors
        no_adults_same_tour = int(row[7]) if len(row) > 7 and row[7] else 0
        no_children_same_tour = int(row[8]) if len(row) > 8 and row[8] else 0
        no_free_of_charge_same_tour = int(row[9]) if len(row) > 9 and row[9] else 0

        if any([no_adults, no_children, no_free_of_charge]) > 0:
            park_booking = ParkBooking.objects.create(
                booking=booking,
                park_id=park_id,
                arrival=datetime.strptime(arrival, "%Y-%m-%d").date(),
                no_adults=no_adults,
                no_children=no_children,
                no_free_of_charge=no_free_of_charge,
                cost=no_adults * park.adult_price + no_children * park.child_price,
                no_adults_same_tour=no_adults_same_tour,
                no_children_same_tour=no_children_same_tour,
                no_free_of_charge_same_tour=no_free_of_charge_same_tour,
                same_tour_group=same_tour_group,
            )
    if not park_booking:
        raise ValidationError("Must have at least one person visiting the park")

    return booking


"""
TEST 1:
1. create 1 Organisation:
   a. monthly_invoicing_allowed = True
   b. monthly_invoicing_period = 5 (create invoice 0 days from 1st of the month)
   c. monthly_payment_due = 20 (set settlement_date to 20 days after invoice created)
2. For Org, create 2 or 3 bookings, add parks --> pre-date booking to last month
3. run monthly invoice script:
   a. confirm monthly_script SKIPS invoice creation, if executed before the invoicing date (1st of the month + monthly_invoicing_period(5) --> before 6th day of the month)
   b. confirm monthly_script creates invoice, if executed after the invoicing date (1st of the month + monthly_invoicing_period(5) --> on or after 6th of the month)
   b. confirm the created invoice has the correct payment date printed on the PDF (invoice_created + monthly_invoicing_period(20) --> 26th of the month)
4. confirm cannot re-create invoice again for this booking

TEST 2:
1. create 2 Organisations (with different invoicing periods):
   ORG_1:
           a. monthly_invoicing_allowed = True
           b. monthly_invoicing_period = 3 (create invoice 3 days from 1st of the month)
           c. monthly_payment_due = 20 (set settlement_date to 20 days after invoice created)
   ORG_2:
           a. monthly_invoicing_allowed = True
           b. monthly_invoicing_period = 5 (create invoice 5 days from 1st of the month)
           c. monthly_payment_due = 20 (set settlement_date to 20 days after invoice created)
2. For Org_1, create 2 or 3 bookings, add parks --> pre-date booking to last month
3. For Org_3, create 2 or 3 bookings, add parks --> pre-date booking to last month
4. run monthly invoice script:
   a. confirm monthly_script SKIPS invoice creation (for both Orgs), if executed before the invoicing date (1st of the month + monthly_invoicing_period(3) --> before 4th day of the month)
   b. confirm monthly_script creates invoice for Org_1 only, if executed after the Org_1 invoicing date (1st of the month + monthly_invoicing_period(3) --> on or after 4th of the month)
   c. confirm monthly_script creates invoice for Org_2 only, if executed after the Org_2 invoicing date (1st of the month + monthly_invoicing_period(5) --> on or after 6th of the month)
   d. confirm the Org_1 invoice has the correct payment date printed on the PDF (invoice_created_date + monthly_invoicing_period(20) --> 24h of the month)
   e. confirm the Org_2 invoice has the correct payment date printed on the PDF (invoice_created_date + monthly_invoicing_period(20) --> 26 of the month)
4. confirm cannot re-create invoices again for these booking



"""


def create_monthly_invoice(user, offset_months=-1):
    bookings = Booking.objects.filter(
        invoices__isnull=True,
        booking_type=Booking.BOOKING_TYPE_MONTHLY_INVOICING,
        created__month=(timezone.now() + relativedelta(months=offset_months)).month,
    )

    failed_bookings = []
    for booking in bookings:
        with transaction.atomic():
            if is_invoicing_period(booking) and is_monthly_invoicing_allowed(booking):
                try:
                    logger.info(
                        f"Creating monthly invoice for booking {booking.admission_number}"
                    )
                    order = create_invoice(booking, payment_method="monthly_invoicing")
                    invoice = Invoice.objects.get(order_number=order.number)
                    # invoice.settlement_date = calc_payment_due_date(booking, invoice.created + relativedelta(months=1))
                    # invoice.save()

                    deferred_payment_date = calc_payment_due_date(
                        booking, invoice.created
                    )
                    BookingInvoice.objects.create(
                        booking=booking,
                        invoice_reference=invoice.reference,
                        payment_method=invoice.payment_method,
                        deferred_payment_date=deferred_payment_date,
                    )

                    recipients = list(
                        set(booking.proposal.applicant_email, user.email)
                    )  # unique list
                    send_monthly_invoice_tclass_email_notification(
                        user, booking, invoice, recipients=recipients
                    )
                    ProposalUserAction.log_action(
                        booking.proposal,
                        ProposalUserAction.ACTION_SEND_MONTHLY_INVOICE.format(
                            invoice.reference,
                            booking.proposal.id,
                            ", ".join(recipients),
                        ),
                        user,
                    )
                except Exception as e:
                    logger.exception(
                        f"Failed to create monthly invoice for booking_id {booking.id}",
                        exc_info=e,
                    )
                    failed_bookings.append(booking.id)

    return failed_bookings


def create_monthly_confirmation(user, booking):
    """From 'Park Entry Fees' payment screen, monthly invoicing creates invoice later (the next month), so immediately we only send a confirmation.
    For more parks/arrival_dates booked for the same licence, the monthly confirmation pdf is appended with all the park entries for that given month.
    """

    failed_bookings = []
    with transaction.atomic():
        if (
            booking.booking_type == Booking.BOOKING_TYPE_MONTHLY_INVOICING
            and booking.proposal.org_applicant
            and is_monthly_invoicing_allowed(booking)
        ):
            try:
                recipients = list(
                    set(booking.proposal.applicant_email, user.email)
                )  # unique list
                send_monthly_confirmation_tclass_email_notification(
                    user, booking, recipients=recipients
                )
                ProposalUserAction.log_action(
                    booking.proposal,
                    ProposalUserAction.ACTION_SEND_MONTHLY_CONFIRMATION.format(
                        booking.id, booking.proposal.id, ", ".join(recipients)
                    ),
                    user,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send Monthly Confirmation email for booking_id {booking.id}"
                )
                logger.error(f"{e}")
                failed_bookings.append(booking.id)

    return failed_bookings


def create_bpay_invoice(user, booking):

    failed_bookings = []
    with transaction.atomic():
        if (
            booking.booking_type == Booking.BOOKING_TYPE_INTERNET
            and booking.proposal.org_applicant
            and booking.proposal.org_applicant.bpay_allowed
        ):
            try:
                now = timezone.now().date()
                dt = date(now.year, now.month, 1) + relativedelta(months=1)
                logger.info(
                    f"Creating BPAY invoice for booking {booking.admission_number}"
                )
                order = create_invoice(booking, payment_method="bpay")
                invoice = Invoice.objects.get(order_number=order.number)
                # invoice.settlement_date = calc_payment_due_date(booking, dt) - relativedelta(days=1)
                # invoice.save()

                deferred_payment_date = calc_payment_due_date(
                    booking, dt
                ) - relativedelta(days=1)
                BookingInvoice.objects.create(
                    booking=booking,
                    invoice_reference=invoice.reference,
                    payment_method=invoice.payment_method,
                    deferred_payment_date=deferred_payment_date,
                )

                # send_monthly_invoice_tclass_email_notification(user, booking, invoice, recipients=[booking.proposal.applicant_email])
                recipients = list(
                    set(booking.proposal.applicant_email, user.email)
                )  # unique list
                send_invoice_tclass_email_notification(
                    user, booking, invoice, recipients=recipients
                )
                send_confirmation_tclass_email_notification(
                    user, booking, invoice, recipients=recipients
                )
                ProposalUserAction.log_action(
                    booking.proposal,
                    ProposalUserAction.ACTION_SEND_BPAY_INVOICE.format(
                        invoice.reference, booking.proposal.id, ", ".join(recipients)
                    ),
                    user,
                )
            except Exception as e:
                logger.error(
                    f"Failed to create BPAY invoice for booking_id {booking.id}"
                )
                logger.error(f"{e}")
                failed_bookings.append(booking.id)

    return failed_bookings


def create_other_invoice(user, booking):
    """This method allows internal payments officer to pay via ledger directly i.e. over the phone credit card details or cheque by post or cash etc

    Currently not USED in COLS (Only Payments by CC, BPAY and Monthly Invoicing is allowed), but implemented for use possibly in the future
    """

    failed_bookings = []
    with transaction.atomic():
        # if booking.booking_type == Booking.BOOKING_TYPE_RECEPTION and booking.proposal.org_applicant.other_allowed:
        if booking.booking_type == Booking.BOOKING_TYPE_RECEPTION:
            try:
                now = timezone.now().date()
                dt = date(now.year, now.month, 1) + relativedelta(months=1)
                logger.info(
                    f"Creating OTHER (CASH/CHEQUE) invoice for booking {booking.admission_number}"
                )
                order = create_invoice(booking, payment_method="other")
                invoice = Invoice.objects.get(order_number=order.number)

                deferred_payment_date = calc_payment_due_date(
                    booking, dt
                ) - relativedelta(days=1)
                book_inv = BookingInvoice.objects.create(
                    booking=booking,
                    invoice_reference=invoice.reference,
                    payment_method=invoice.payment_method,
                    deferred_payment_date=deferred_payment_date,
                )

                # send_monthly_invoice_tclass_email_notification(user, booking, invoice, recipients=[booking.proposal.applicant_email])
                # ProposalUserAction.log_action(booking.proposal,ProposalUserAction.ACTION_SEND_MONTHLY_INVOICE.format(booking.proposal.id),booking.proposal.applicant_email)
            except Exception as e:
                logger.error(
                    f"Failed to create OTHER invoice for booking_id {booking.id}"
                )
                logger.error(f"{e}")
                failed_bookings.append(booking.id)

    return failed_bookings


def calc_payment_due_date(booking, _date):
    org_applicant = booking.proposal.org_applicant
    if (
        isinstance(org_applicant, Organisation)
        and org_applicant.monthly_payment_due_period > 0
    ):
        return _date + relativedelta(days=org_applicant.monthly_payment_due_period)
    return _date + relativedelta(days=30)


def is_invoicing_period(booking):
    org_applicant = booking.proposal.org_applicant
    if isinstance(org_applicant, Organisation):
        return timezone.now().day >= org_applicant.monthly_invoicing_period
    return False


def is_monthly_invoicing_allowed(booking):
    org_applicant = booking.proposal.org_applicant
    if isinstance(org_applicant, Organisation):
        return (
            booking.booking_type == Booking.BOOKING_TYPE_MONTHLY_INVOICING
            and org_applicant
            and org_applicant.monthly_invoicing_allowed
        )
    return False


def get_session_booking(session):
    booking_id = session.get("cols_booking")
    if not booking_id:
        return None

    return Booking.objects.filter(id=booking_id).first()


def set_session_booking(session, booking):
    session["cols_booking"] = booking.id
    session.modified = True


def delete_session_booking(session):
    if "cols_booking" in session:
        del session["cols_booking"]
        session.modified = True


def get_session_application_invoice(session):
    """Application Fee session ID"""
    if "cols_app_invoice" in session:
        application_fee_id = session["cols_app_invoice"]
    else:
        raise Exception("Application not in Session")

    try:
        return ApplicationFee.objects.get(id=application_fee_id)
    except Invoice.DoesNotExist:
        raise Exception(f"Application not found for application {application_fee_id}")


def set_session_application_invoice(session, application_fee):
    logger.info("Application Fee session ID Set")
    """Application Fee session ID"""
    session["cols_app_invoice"] = application_fee.id
    session.modified = True


def delete_session_application_invoice(session):
    """Application Fee session ID"""
    if "cols_app_invoice" in session:
        del session["cols_app_invoice"]
        session.modified = True


# Events - Compliance
def get_session_compliance_invoice(session):
    """Compliance Fee session ID"""
    if "cols_comp_invoice" in session:
        compliance_fee_id = session["cols_comp_invoice"]
    else:
        raise Exception("Compliance not in Session")

    try:
        return ComplianceFee.objects.get(id=compliance_fee_id)
    except Invoice.DoesNotExist:
        raise Exception(
            f"Compliance record not found for compliance {compliance_fee_id}"
        )


def set_session_compliance_invoice(session, compliance_fee):
    """Compliance Fee session ID"""
    session["cols_comp_invoice"] = compliance_fee.id
    session.modified = True


def delete_session_compliance_invoice(session):
    """Compliance Fee session ID"""
    if "cols_comp_invoice" in session:
        del session["cols_comp_invoice"]
        session.modified = True


# Filming - Fee (Application and Licence)
def get_session_filming_invoice(session):
    """Filming Fee session ID"""
    if "cols_filming_invoice" in session:
        filming_fee_id = session["cols_filming_invoice"]
    else:
        raise Exception("Filming not in Session")

    try:
        return FilmingFee.objects.get(id=filming_fee_id)
    except Invoice.DoesNotExist:
        raise Exception(f"Filming record not found for filming_fee {filming_fee_id}")


def set_session_filming_invoice(session, filming_fee):
    """Filming Fee session ID"""
    session["cols_filming_invoice"] = filming_fee.id
    session.modified = True


def delete_session_filming_invoice(session):
    """Filming Fee session ID"""
    if "cols_filming_invoice" in session:
        del session["cols_filming_invoice"]
        session.modified = True


def create_compliance_fee_lines(
    compliance, invoice_text=None, vouchers=[], internal=False
):
    """Create the ledger lines - line item for compliance fee sent to payment system"""

    def add_line_item(park, price, no_persons):
        if no_persons > 0:
            return {
                "ledger_description": f"{park.name}, participants: {no_persons}",
                "oracle_code": park.oracle_code(compliance.proposal.application_type),
                #'oracle_code': 'NNP415 GST',
                "price_incl_tax": float(price),
                "price_excl_tax": price,  # Compliance 'park' participants - this is GST Emempt
                #'price_excl_tax':  float(price) if park.is_gst_exempt else round(float(calculate_excl_gst(price)), 2),
                "quantity": 1,  # no_persons,
            }
        return None

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    events_park_price = compliance.proposal.application_type.events_park_fee
    events_parks = compliance.proposal.events_parks.all().distinct("park__name")
    # cost_per_park = (events_park_price * compliance.num_participants) / len(events_parks)
    invoice_total = events_park_price * compliance.num_participants
    if settings.DEBUG:
        # since Ledger UAT only handles whole integer total
        invoice_total = round(invoice_total, 0)

    try:
        alloc_per_park = round(invoice_total / len(events_parks), 2)
    except:
        alloc_per_park = 0

    try:
        rounding_error = round(invoice_total - (alloc_per_park * len(events_parks)), 2)
    except:
        rounding_error = 0

    lines = []
    for idx, events_park in enumerate(events_parks, 1):
        park = events_park.park
        if idx == len(events_parks):
            # add rounding error to last line/product
            lines.append(
                add_line_item(
                    park,
                    price=alloc_per_park + rounding_error,
                    no_persons=compliance.num_participants,
                )
            )
        else:
            lines.append(
                add_line_item(
                    park, price=alloc_per_park, no_persons=compliance.num_participants
                )
            )

    # logger.info('{}'.format(lines))
    return lines


def create_fee_lines(proposal, invoice_text=None, vouchers=[], internal=False):
    lines = []
    if proposal.application_type.name == ApplicationType.TCLASS:
        return create_tclass_fee_lines(proposal, invoice_text, vouchers, internal)
    elif proposal.application_type.name == ApplicationType.EVENT:
        return create_event_fee_lines(proposal, invoice_text, vouchers, internal)

    return lines


def create_tclass_fee_lines(proposal, invoice_text=None, vouchers=[], internal=False):
    """Create the ledger lines - line item for application fee sent to payment system"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    application_price = proposal.application_type.application_fee
    licence_price = proposal.licence_fee_amount

    if proposal.application_type.name == ApplicationType.TCLASS:
        if proposal.org_applicant.apply_application_discount:
            application_discount = min(
                proposal.org_applicant.application_discount, application_price
            )
        if proposal.org_applicant.apply_licence_discount:
            licence_discount = min(
                proposal.org_applicant.licence_discount, licence_price
            )

    line_items = [
        {
            "ledger_description": f"Application Fee - {now} - {proposal.lodgement_number}",
            "oracle_code": proposal.application_type.oracle_code_application,
            "price_incl_tax": application_price,
            "price_excl_tax": application_price,
            "quantity": 1,
        },
        {
            "ledger_description": f"Licence Charge {proposal.other_details.get_preferred_licence_period_display()} - {now} - {proposal.lodgement_number}",
            "oracle_code": proposal.application_type.oracle_code_licence,
            "price_incl_tax": licence_price,
            "price_excl_tax": licence_price,
            "quantity": 1,
        },
    ]

    # Add fee Waiver To T Class, if any
    if (
        proposal.application_type.name == ApplicationType.TCLASS
        and proposal.org_applicant
    ):
        if proposal.org_applicant.apply_application_discount:
            line_items += [
                {
                    "ledger_description": f"Application Fee Waiver - {now} - {proposal.lodgement_number}",
                    "oracle_code": proposal.application_type.oracle_code_application,
                    "price_incl_tax": -application_discount,
                    "price_excl_tax": -application_discount,
                    "quantity": 1,
                }
            ]
        if proposal.org_applicant.apply_licence_discount:
            line_items += [
                {
                    "ledger_description": f"Licence Charge Waiver - {now} - {proposal.lodgement_number}",
                    "oracle_code": proposal.application_type.oracle_code_application,
                    "price_incl_tax": -licence_discount,
                    "price_excl_tax": -licence_discount,
                    "quantity": 1,
                }
            ]

    logger.info(f"{line_items}")
    return line_items


def create_event_fee_lines(proposal, invoice_text=None, vouchers=[], internal=False):
    """EVENT: Create the ledger lines - line item for application fee sent to payment system"""

    def get_application_fee():
        application_fee = proposal.application_type.application_fee

        org = proposal.org_applicant
        if org.charge_once_per_year:
            year_start = date(
                proposal.event_activity.commencement_date.year,
                org.charge_once_per_year.month,
                org.charge_once_per_year.day,
            )
            year_end = year_start + relativedelta(years=1)
            fees_paid = [
                (p, p.fee_amount)
                for p in Proposal.objects.filter(
                    org_applicant=org,
                    application_type__name=ApplicationType.EVENT,
                    event_activity__commencement_date__gte=year_start,
                    event_activity__completion_date__lt=year_end,
                )
                if p.fee_amount and p.fee_amount != "null" and float(p.fee_amount) > 0.0
            ]

            logger.info(
                rf"{proposal} - {org}: Fees paid between {year_start} - {year_end}\{fees_paid})"
            )
            if fees_paid:
                # application fee has already been paid at least once for the calendar period
                application_fee = Decimal("0.0")
                logger.info(
                    f"{proposal} - {org}: Setting Application Fee to 0.0 (free free for period {year_start} - {year_end})"
                )

        return application_fee

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    application_price = get_application_fee()

    if proposal.application_type.name == ApplicationType.EVENT:
        # There is no Licence fee for Event application.
        line_items = [
            {
                "ledger_description": f"Application Fee - {now} - {proposal.lodgement_number}",
                "oracle_code": proposal.application_type.oracle_code_application,
                "price_incl_tax": application_price,
                "price_excl_tax": application_price,
                "quantity": 1,
            },
        ]
    logger.info(f"{line_items}")
    return line_items


def create_filming_park_fee_lines(proposal, licence_fee, licence_text, filming_period):
    """Create the ledger lines, line items for each park - filming licence fee divided evenly and sent to payment system"""

    def add_line_item(park, price):
        return {
            "ledger_description": f"{park.name} ({licence_text} - {filming_period})",
            # Licence fees use the licence oracle code (GST-exempt), not the park
            # entry fee oracle code. Licence charges are GST exempt for all
            # licence types, regardless of the park's is_gst_exempt flag (that
            # flag only governs park entry fees).
            "oracle_code": proposal.application_type.oracle_code_licence,
            "price_incl_tax": float(price),
            "price_excl_tax": float(price),
            "quantity": 1,  # no_persons,
        }

    filming_parks = proposal.filming_parks.all().distinct("park__name")
    invoice_total = licence_fee
    if (
        settings.ROUND_INVOICE_TOTALS
    ):  # TODO adding a rounding env var setting, do not rely on debug
        # since Ledger UAT only handles whole integer total
        invoice_total = round(invoice_total, 0)

    alloc_per_park = (
        round(invoice_total / len(filming_parks), 2) if len(filming_parks) > 0 else 0
    )
    rounding_error = round(invoice_total - (alloc_per_park * len(filming_parks)), 2)

    lines = []
    for idx, filming_park in enumerate(filming_parks, 1):
        park = filming_park.park
        if idx == len(filming_parks):
            # add rounding error to last line/product
            lines.append(add_line_item(park, price=alloc_per_park + rounding_error))
        else:
            lines.append(add_line_item(park, price=alloc_per_park))

    # logger.info('{}'.format(lines))
    return lines


def create_filming_fee_lines(proposal, invoice_text=None, vouchers=[], internal=False):
    if "motion_film" in proposal.filming_activity.film_type:
        # Filming (and perhaps Photography)
        desc = "Filming/Photography"
        if proposal.filming_licence_charge_type == proposal.HALF_DAY_CHARGE:
            licence_fee = proposal.application_type.filming_fee_half_day
            licence_text = "Half day"
        elif proposal.filming_licence_charge_type == proposal.FULL_DAY_CHARGE:
            licence_fee = proposal.application_type.filming_fee_full_day
            licence_text = "Full day"
        elif proposal.filming_licence_charge_type == proposal.TWO_DAYS_CHARGE:
            licence_fee = proposal.application_type.filming_fee_2days
            licence_text = "Two days"
        elif proposal.filming_licence_charge_type == proposal.THREE_OR_MORE_DAYS_CHARGE:
            licence_fee = proposal.application_type.filming_fee_3days
            licence_text = "Three days or more"
        elif proposal.filming_licence_charge_type == proposal.NON_STANDARD_CHARGE:
            licence_fee = proposal.filming_non_standard_charge
            licence_text = "Non-standard charge"
        else:
            raise Exception("Unknown filming charge type")
    else:
        # Photography
        desc = "Photography"
        if proposal.filming_licence_charge_type == proposal.HALF_DAY_CHARGE:
            licence_fee = proposal.application_type.photography_fee_half_day
            licence_text = "Half day"
        elif proposal.filming_licence_charge_type == proposal.FULL_DAY_CHARGE:
            licence_fee = proposal.application_type.photography_fee_full_day
            licence_text = "Full day"
        elif proposal.filming_licence_charge_type == proposal.TWO_DAYS_CHARGE:
            licence_fee = proposal.application_type.photography_fee_2days
            licence_text = "Two days"
        elif proposal.filming_licence_charge_type == proposal.THREE_OR_MORE_DAYS_CHARGE:
            licence_fee = proposal.application_type.photography_fee_3days
            licence_text = "Three days or more"
        elif proposal.filming_licence_charge_type == proposal.NON_STANDARD_CHARGE:
            licence_fee = proposal.filming_non_standard_charge
            licence_text = "Non-standard charge"
        else:
            raise Exception("Unknown filming charge type")

    application_fee = proposal.application_type.application_fee
    filming_period = f"{proposal.filming_activity.commencement_date} - {proposal.filming_activity.completion_date}"

    lines_app = [
        {
            "ledger_description": f"{desc} Application Fee - {proposal.lodgement_number}",
            "oracle_code": proposal.application_type.oracle_code_application,
            "price_incl_tax": str(application_fee),
            "price_excl_tax": str(application_fee),
            "quantity": 1,
        }
    ]
    lines_parks_aggregated = [
        {
            "ledger_description": f"{desc} Licence Fee ({licence_text} - {filming_period}) - {proposal.lodgement_number}",
            "oracle_code": proposal.application_type.oracle_code_licence,  # this line is dummy, for aggregated (externally generated) invoice
            "price_incl_tax": str(licence_fee),
            "price_excl_tax": str(licence_fee),
            "quantity": 1,
        }
    ]
    lines_aggregated = lines_app + lines_parks_aggregated
    lines = lines_app + create_filming_park_fee_lines(
        proposal, licence_fee, licence_text, filming_period
    )
    return lines, lines_aggregated


def create_lines(request, invoice_text=None, vouchers=[], internal=False):
    """Create the ledger lines - line items for invoice sent to payment system"""

    def add_line_item(park, arrival, age_group, price, no_persons):
        # Park prices are GST-inclusive per person. Round reverse GST per person
        # before multiplying so invoice line totals remain cent-accurate.
        price = round(float(price), 2)
        # if no_persons > 0 or (same_tour_group and no_persons >= 0):
        if no_persons > 0:
            price_incl_tax = round(price * no_persons, 2)
            price_excl_tax = (
                price_incl_tax
                if park.is_gst_exempt
                else round(
                    round(price / (1 + settings.LEDGER_GST / 100), 2) * no_persons,
                    2,
                )
            )
            return {
                "ledger_description": f"{park.name} - {arrival} - {age_group}",
                #'oracle_code': park.oracle_code(ApplicationType.TCLASS).encode('utf-8'),
                "oracle_code": park.oracle_code(ApplicationType.TCLASS),
                "price_incl_tax": price_incl_tax,
                "price_excl_tax": price_excl_tax,
                "quantity": no_persons,
            }
        return None

    lines = []
    tbody = json.loads(request.POST["payment"])["tbody"]
    for row in tbody:
        park_id = row[0]["value"]
        arrival = row[1]
        same_tour_group = True if row[2] else False
        no_adults = int(row[3]) if row[3] else 0
        no_children = int(row[4]) if row[4] else 0
        no_free_of_charge = int(row[5]) if row[5] else 0
        park = Park.objects.get(id=park_id)

        # same tour group visitors
        no_adults_same_tour = (
            int(row[7]) if (row[7] != "" and row[7] is not None) else None
        )
        no_children_same_tour = (
            int(row[8]) if (row[8] != "" and row[8] is not None) else None
        )
        no_free_of_charge_same_tour = (
            int(row[9]) if (row[9] != "" and row[9] is not None) else None
        )

        # no_adults = no_adults if no_adults_same_tour==0 else no_adults_same_tour
        # no_children = no_children if no_children_same_tour==0 else no_children_same_tour
        # no_free_of_charge = no_free_of_charge if no_free_of_charge_same_tour==0 else no_free_of_charge_same_tour

        if same_tour_group and no_adults_same_tour is not None:
            if no_adults_same_tour > 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Adult (Same Tour Group, Total {no_adults})",
                        price=park.adult_price,
                        no_persons=no_adults_same_tour,
                    )
                )
            elif no_adults_same_tour == 0 and no_adults != 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Adult (Same Tour Group, Total {no_adults})",
                        price=0.0,
                        no_persons=no_adults,
                    )
                )
        elif no_adults > 0:
            lines.append(
                add_line_item(
                    park, arrival, "Adult", price=park.adult_price, no_persons=no_adults
                )
            )

        if same_tour_group and no_children_same_tour is not None:
            if no_children_same_tour > 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Child (Same Tour Group, Total {no_children})",
                        price=park.child_price,
                        no_persons=no_children_same_tour,
                    )
                )
            elif no_children_same_tour == 0 and no_children != 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Child (Same Tour Group, Total {no_children})",
                        price=0.0,
                        no_persons=no_children,
                    )
                )
        elif no_children > 0:
            lines.append(
                add_line_item(
                    park,
                    arrival,
                    "Child",
                    price=park.child_price,
                    no_persons=no_children,
                )
            )

        if same_tour_group and no_free_of_charge_same_tour is not None:
            if no_free_of_charge_same_tour > 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Free (Same Tour Group, Total {no_free_of_charge})",
                        price=0.0,
                        no_persons=no_free_of_charge_same_tour,
                    )
                )
            elif no_free_of_charge_same_tour == 0 and no_free_of_charge != 0:
                lines.append(
                    add_line_item(
                        park,
                        arrival,
                        f"Free (Same Tour Group, Total {no_free_of_charge})",
                        price=0.0,
                        no_persons=no_free_of_charge,
                    )
                )
        elif no_free_of_charge > 0:
            lines.append(
                add_line_item(
                    park, arrival, "Free", price=0.0, no_persons=no_free_of_charge
                )
            )

    return lines


def checkout(
    request,
    proposal,
    lines,
    return_url,
    return_preload_url,
    invoice_text=None,
    vouchers=[],
    reference=None,
):

    if not reference:
        reference = proposal.lodgement_number if proposal else None

    if not reference:
        raise serializers.ValidationError("No record reference")

    try:
        email_user_id = proposal.submitter.id if proposal.submitter else request.user.id
    except:
        raise serializers.ValidationError("No submitter or request user id")

    basket_params = {
        "products": lines,
        "vouchers": vouchers,
        "system": settings.PAYMENT_SYSTEM_ID,
        "custom_basket": True,
        "tax_override": True,
        "booking_reference": reference,
        "booking_reference_link": reference,
        "fallback_url": request.build_absolute_uri("/"),
        "no_payment": False,
    }
    # Note: this solution circumvents json.dumps from throwing an error (can not serialize Decimal)
    basket_params = json.loads(json.dumps(basket_params, cls=DecimalEncoder))

    basket_session = create_basket_session(request, email_user_id, basket_params)

    print(f"Return URL: {return_url}, Return Preload URL: {return_preload_url}")
    checkout_params = {
        "system": settings.PAYMENT_SYSTEM_ID,
        "fallback_url": request.build_absolute_uri("/"),
        "return_url": return_url,
        "return_preload_url": return_preload_url,
        "force_redirect": True,
        "invoice_text": invoice_text,
        # "proxy": True if is_internal(request) else False,
        "session_type": "ledger_api",
        "basket_owner": email_user_id,
    }

    logger.info(
        f"Creating checkout session with checkout parameters: {checkout_params}"
    )

    create_checkout_session(request, checkout_params)

    logger.info("Redirecting user to ledgergw payment details page.")
    logger.info(reverse("ledgergw-payment-details"))
    response = HttpResponse(
        "<script> window.location='"
        + reverse("ledgergw-payment-details")
        + "';</script> <a href='"
        + reverse("ledgergw-payment-details")
        + "'> Redirecting please wait: "
        + reverse("ledgergw-payment-details")
        + "</a>"
    )
    return response


def checkout_existing_invoice(
    request,
    reference,
    invoice,
    return_url_ns="public_booking_success",
):

    return_url = request.build_absolute_uri(
        reverse(return_url_ns, kwargs={"reference": reference})
    )

    fallback_url = request.build_absolute_uri("/")
    payment_session = generate_payment_session(
        request, invoice.reference, return_url, fallback_url
    )
    if payment_session.get("status", None) != status.HTTP_200_OK:
        raise ValidationError(
            payment_session.get("message", "Error generating payment session")
        )

    return HttpResponseRedirect(payment_session["payment_url"])


def oracle_integration(date, override):
    system = "0557"
    oracle_parser(date, system, "Commercial Operator Licensing", override=override)


def redirect_to_zero_payment_view(request, proposal, lines):
    """
    redirect to Zero Payment preview, instead of Credit Card checkout view
    """
    template_name = "commercialoperator/booking/preview.html"

    if proposal.allow_full_discount:
        logger.info(
            "{} built payment line item {} for Application Fee and handing over to ZERO Payment preview".format(
                f"User {proposal.submitter.get_full_name()} with id {proposal.submitter.id}",
                proposal.id,
            )
        )
        basket = createCustomBasket(lines, request.user, settings.PAYMENT_SYSTEM_ID)
        context = {
            "basket": basket,
            "lines": basket.lines.all(),
            "line_details": basket.lines.all(),  # request.POST['payment'],
            "proposal_id": proposal.id,
            "payment_method": "ZERO",
            "redirect_url": reverse("zero_fee_success"),
        }
        return render(request, template_name, context)


def create_invoice(booking, payment_method="bpay"):
    """
    This will create and invoice and order from a basket bypassing the session
    and payment bpoint code constraints.
    """

    from ledger_api_client.ledger_models import EmailUserRO as EmailUser

    from commercialoperator.components.segregation.classes import CreateInvoiceBasket
    from commercialoperator.components.segregation.utils import createCustomBasket

    # products = Booking.objects.last().as_line_items
    products = booking.as_line_items
    try:
        user = EmailUser.objects.get(email=booking.proposal.applicant_email.lower())
    except Exception:
        user = EmailUser.objects.get(email=booking.proposal.submitter.email.lower())

    if payment_method == "monthly_invoicing":
        invoice_text = "Monthly Payment Invoice"
    elif payment_method == "bpay":
        invoice_text = "BPAY Payment Invoice"
    else:
        invoice_text = "Payment Invoice"

    basket = createCustomBasket(products, user, settings.PAYMENT_SYSTEM_ID)
    order = CreateInvoiceBasket(
        payment_method=payment_method, system=settings.PAYMENT_SYSTEM_PREFIX
    ).create_invoice_and_order(
        basket, 0, None, None, user=user, invoice_text=invoice_text
    )

    return order


def get_invoice_properties(invoice_id):
    import ledger_api_client.utils as ledger_utils

    invoice_properties_response = ledger_utils.get_invoice_properties(invoice_id)

    if invoice_properties_response.get("status", None) != status.HTTP_200_OK:
        logger.error(
            f"Invoice properties not found for invoice {invoice_id}: {invoice_properties_response['message']}"
        )
        return {}

    return invoice_properties_response.get("data", {})


def get_invoice_properties_all():
    invoices = Invoice.objects.all()
    # NOTE: (Karsten) Caching
    invoices_properties = [
        get_invoice_properties(invoice.id) for invoice in invoices if invoice.id
    ]
    return [inv_props for inv_props in invoices_properties if inv_props]


def get_invoice_pdf(invoice_reference):
    api_key = settings.LEDGER_API_KEY
    url = (
        settings.LEDGER_API_URL
        + "/ledgergw/invoice-pdf/"
        + api_key
        + "/"
        + invoice_reference
    )
    return requests.get(url=url)
