from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.urls import re_path as url
from django_media_serv.urls import urlpatterns as media_serv_patterns
from ledger_api_client.urls import urlpatterns as ledger_patterns
from rest_framework import routers

from commercialoperator import views
from commercialoperator.admin import admin
from commercialoperator.components.approvals import api as approval_api
from commercialoperator.components.bookings import api as booking_api
from commercialoperator.components.bookings import views as booking_views
from commercialoperator.components.compliances import api as compliances_api
from commercialoperator.components.main import api as main_api
from commercialoperator.components.organisations import api as org_api
from commercialoperator.components.organisations import views as organisation_views

# T Class
from commercialoperator.components.proposals import api as proposal_api

# Event
from commercialoperator.components.proposals import api_event as proposal_api_event

# Filming
from commercialoperator.components.proposals import api_filming as proposal_api_filming
from commercialoperator.components.proposals import views as proposal_views
from commercialoperator.components.users import api as users_api

# API patterns
router = routers.DefaultRouter()
router.include_root_view = settings.SHOW_ROOT_API
router.register(r"organisations", org_api.OrganisationViewSet, "organisations")
router.register(r"proposal", proposal_api.ProposalViewSet, "proposal")
router.register(r"proposal_park", proposal_api.ProposalParkViewSet, "proposal_park")
router.register(
    r"proposal_paginated", proposal_api.ProposalPaginatedViewSet, "proposal_paginated"
)
router.register(
    r"approval_paginated", approval_api.ApprovalPaginatedViewSet, "approval_paginated"
)
router.register(
    r"booking_paginated", booking_api.BookingPaginatedViewSet, "booking_paginated"
)
router.register(
    r"parkbooking_paginated",
    booking_api.ParkBookingPaginatedViewSet,
    "parkbooking_paginated",
)
router.register(
    r"compliance_paginated",
    compliances_api.CompliancePaginatedViewSet,
    "compliance_paginated",
)
router.register(r"referrals", proposal_api.ReferralViewSet, "referrals")
router.register(r"approvals", approval_api.ApprovalViewSet, "approvals")
router.register(
    r"overdue_invoices", booking_api.OverdueBookingInvoiceViewSet, "overdue_invoices"
)
router.register(r"compliances", compliances_api.ComplianceViewSet, "compliances")
router.register(
    r"proposal_requirements",
    proposal_api.ProposalRequirementViewSet,
    "proposal_requirements",
)
router.register(
    r"proposal_standard_requirements",
    proposal_api.ProposalStandardRequirementViewSet,
    "proposal_standard_requirements",
)
router.register(
    r"organisation_requests",
    org_api.OrganisationRequestsViewSet,
    "organisation_requests",
)
router.register(r"users", users_api.UserViewSet)
router.register(
    r"amendment_request", proposal_api.AmendmentRequestViewSet, "amendment_request"
)
router.register(
    r"compliance_amendment_request",
    compliances_api.ComplianceAmendmentRequestViewSet,
    "compliance_amendment_request",
)
router.register(r"regions", main_api.RegionViewSet, "regions")
router.register(r"districts", main_api.DistrictViewSet, "districts")
router.register(r"global_settings", main_api.GlobalSettingsViewSet, "global_settings")
router.register(r"activity_matrix", main_api.ActivityMatrixViewSet, "activity_matrix")
router.register(
    r"application_types", main_api.ApplicationTypeViewSet, "application_types"
)
router.register(r"access_types", main_api.AccessTypeViewSet, "access_types")
router.register(r"vessels", proposal_api.VesselViewSet, "vessels")
router.register(r"assessments", proposal_api.ProposalAssessmentViewSet, "assessments")
router.register(r"parks", main_api.ParkViewSet, "parks")
router.register(
    r"tclass_container_land",
    main_api.LandActivityTabViewSet,
    basename="tclass_container_land",
)
router.register(
    r"tclass_container_marine",
    main_api.MarineActivityTabViewSet,
    basename="tclass_container_marine",
)
router.register(r"trails", main_api.TrailViewSet, "trails")
router.register(r"vehicles", proposal_api.VehicleViewSet, "vehicles")
router.register(r"land_activities", main_api.LandActivitiesViewSet, "land_activities")
router.register(
    r"marine_activities", main_api.MarineActivitiesViewSet, "marine_activities"
)
router.register(
    r"required_documents", main_api.RequiredDocumentViewSet, "required_documents"
)
router.register(r"questions", main_api.QuestionViewSet, "questions")
router.register(
    r"event_trail_container", main_api.TrailTabViewSet, basename="event_trail_container"
)
router.register(
    r"event_park_container",
    main_api.EventsParkTabViewSet,
    basename="event_park_container",
)


# Filming
router.register(
    r"proposal_filming_parks",
    proposal_api_filming.ProposalFilmingParksViewSet,
    "proposal_filming_parks",
)
router.register(
    r"district_proposals", proposal_api.DistrictProposalViewSet, "district_proposals"
)
router.register(
    r"district_proposal_paginated",
    proposal_api.DistrictProposalPaginatedViewSet,
    "district_proposal_paginated",
)

# Events
router.register(
    r"proposal_events_parks",
    proposal_api_event.ProposalEventsParksViewSet,
    "proposal_events_parks",
)
router.register(
    r"abseiling_climbing_activities",
    proposal_api_event.AbseilingClimbingActivityViewSet,
    "abseiling_climbing_activities",
)
router.register(
    r"proposal_pre_event_parks",
    proposal_api_event.ProposalPreEventsParksViewSet,
    "proposal_pre_event_parks",
)
router.register(
    r"proposal_events_trails",
    proposal_api_event.ProposalEventsTrailsViewSet,
    "proposal_events_trails",
)
(
    router.register(
        r"search_proposals",
        proposal_api.SearchProposalsViewSet,
        "search-proposals",
    ),
)

api_patterns = [
    url(
        r"^api/account/$",
        users_api.GetLedgerAccount.as_view(),
        name="get-ledger-account",
    ),
    url(
        r"^api/request_user_id/$",
        users_api.GetRequestUserID.as_view(),
        name="get-request-user-id",
    ),
    url(r"^api/profile$", users_api.GetProfile.as_view(), name="get-profile"),
    url(r"^api/countries$", users_api.GetCountries.as_view(), name="get-countries"),
    url(
        r"^api/filtered_users$",
        users_api.UserListFilterView.as_view(),
        name="filtered_users",
    ),
    url(
        r"^api/filtered_organisations$",
        org_api.OrganisationListFilterView.as_view(),
        name="filtered_organisations",
    ),
    url(
        r"^api/filtered_payments$",
        approval_api.ApprovalPaymentFilterViewSet.as_view(),
        name="filtered_payments",
    ),
    url(
        r"^api/organisation_access_group_members",
        org_api.OrganisationAccessGroupMembersView.as_view(),
        name="organisation-access-group-members",
    ),
    url(r"^api/", include(router.urls)),
    url(
        r"^api/amendment_request_reason_choices",
        proposal_api.AmendmentRequestReasonChoicesView.as_view(),
        name="amendment_request_reason_choices",
    ),
    url(
        r"^api/compliance_amendment_reason_choices",
        compliances_api.ComplianceAmendmentReasonChoicesView.as_view(),
        name="amendment_request_reason_choices",
    ),
    url(
        r"^api/search_keywords",
        proposal_api.SearchKeywordsView.as_view(),
        name="search_keywords",
    ),
    url(
        r"^api/search_reference",
        proposal_api.SearchReferenceView.as_view(),
        name="search_reference",
    ),
    url(
        r"^api/accreditation_choices",
        proposal_api.AccreditationTypeView.as_view(),
        name="accreditation_choices",
    ),
    url(
        r"^api/tourism_standard_choices",
        proposal_api.TourismStandardsView.as_view(),
        name="tourism_standard_choices",
    ),
    url(
        r"^api/licence_period_choices",
        proposal_api.LicencePeriodChoicesView.as_view(),
        name="licence_period_choices",
    ),
    url(
        r"^api/filming_licence_charge_choices",
        proposal_api.FilmingLicenceChargeView.as_view(),
        name="filming_licence_charge_choices ",
    ),
    # Filming
    url(
        r"^api/filming_activity_tab",
        proposal_api_filming.FilmingActivityTabView.as_view(),
        name="filming_activity_tab",
    ),
]

# URL Patterns
urlpatterns = (
    [
        url(r"^admin/", admin.site.urls, name="admin"),
        url(r"", include(api_patterns)),
        url(r"^$", views.CommercialOperatorRoutingView.as_view(), name="home"),
        url(
            r"^contact/",
            views.CommercialOperatorContactView.as_view(),
            name="ds_contact",
        ),
        url(
            r"^further_info/",
            views.CommercialOperatorFurtherInformationView.as_view(),
            name="ds_further_info",
        ),
        url(r"^internal/", views.InternalView.as_view(), name="internal"),
        url(
            r"^internal/proposal/(?P<proposal_pk>\d+)/referral/(?P<referral_pk>\d+)/$",
            views.ReferralView.as_view(),
            name="internal-referral-detail",
        ),
        url(r"^external/", views.ExternalView.as_view(), name="external"),
        url(r"^profiles/", views.ExternalView.as_view(), name="manage-profiles"),
        url(
            r"^mgt-commands/$",
            views.ManagementCommandsView.as_view(),
            name="mgt-commands",
        ),
        url(
            r"test-emails/$", proposal_views.TestEmailView.as_view(), name="test-emails"
        ),
        url(
            r"^preview/licence-pdf/(?P<proposal_pk>\d+)",
            proposal_views.PreviewLicencePDFView.as_view(),
            name="preview_licence_pdf",
        ),
        url(
            r"^district_preview/licence-pdf/(?P<district_proposal_pk>\d+)",
            proposal_views.PreviewDistrictLicencePDFView.as_view(),
            name="district_preview_licence_pdf",
        ),
        # payment related urls
        url(
            r"^application_fee/(?P<proposal_pk>\d+)/$",
            booking_views.ApplicationFeeView.as_view(),
            name="application_fee",
        ),
        url(
            r"^compliance_fee/(?P<compliance_pk>\d+)/$",
            booking_views.ComplianceFeeView.as_view(),
            name="compliance_fee",
        ),
        url(
            r"^filming_fee/(?P<proposal_pk>\d+)/$",
            booking_views.FilmingFeeView.as_view(),
            name="filming_fee",
        ),
        url(
            r"^payment/(?P<proposal_pk>\d+)/$",
            booking_views.MakePaymentView.as_view(),
            name="make_payment",
        ),
        url(
            r"^payment_deferred/(?P<proposal_pk>\d+)/$",
            booking_views.DeferredInvoicingView.as_view(),
            name="deferred_invoicing",
        ),
        url(
            r"^preview_deferred/(?P<proposal_pk>\d+)/$",
            booking_views.DeferredInvoicingPreviewView.as_view(),
            name="preview_deferred_invoicing",
        ),
        url(
            r"^success/booking_preload/(?P<reference>.+)/",
            booking_views.BookingSuccessViewPreload.as_view(),
            name="public_booking_success_preload",
        ),
        url(
            r"^success/booking/(?P<reference>.+)/",
            booking_views.BookingSuccessView.as_view(),
            name="public_booking_success",
        ),
        url(
            r"^success_preload/fee/(?P<reference>.+)/",
            booking_views.ApplicationFeeSuccessViewPreload.as_view(),
            name="fee_success_preload",
        ),
        url(
            r"^success/fee/(?P<reference>.+)/",
            booking_views.ApplicationFeeSuccessView.as_view(),
            name="fee_success",
        ),
        url(
            r"^success_preload/compliance_fee/(?P<reference>.+)/",
            booking_views.ComplianceFeeSuccessViewPreload.as_view(),
            name="compliance_success_preload",
        ),
        url(
            r"^success/compliance_fee/(?P<reference>.+)/",
            booking_views.ComplianceFeeSuccessView.as_view(),
            name="compliance_fee_success",
        ),
        url(
            r"^success_preload/filming_fee/(?P<reference>.+)/",
            booking_views.FilmingFeeSuccessViewPreload.as_view(),
            name="filming_fee_success_preload",
        ),
        url(
            r"^success/filming_fee/(?P<reference>.+)/",
            booking_views.FilmingFeeSuccessView.as_view(),
            name="filming_fee_success",
        ),
        url(
            r"^cols/payments/invoice-payment-view/(?P<reference>\d+)",
            booking_views.InvoicePaymentView.as_view(),
            name="internal-invoice-payment-view",
        ),
        url(
            r"cols/payments/invoice-pdf/(?P<reference>\d+)",
            booking_views.InvoicePDFView.as_view(),
            name="cols-invoice-pdf",
        ),
        url(
            r"cols/payments/invoice-filmingfee-pdf/(?P<reference>\d+)",
            booking_views.InvoiceFilmingFeePDFView.as_view(),
            name="cols-invoice-filmingfee-pdf",
        ),
        url(
            r"cols/payments/invoice-compliance-pdf/(?P<reference>\d+)",
            booking_views.InvoiceCompliancePDFView.as_view(),
            name="cols-invoice-compliance-pdf",
        ),
        url(
            r"cols/payments/confirmation-pdf/(?P<reference>\d+)",
            booking_views.ConfirmationPDFView.as_view(),
            name="cols-confirmation-pdf",
        ),
        url(
            r"cols/payments/monthly-confirmation-pdf/booking/(?P<id>\d+)",
            booking_views.MonthlyConfirmationPDFBookingView.as_view(),
            name="cols-monthly-confirmation-pdf",
        ),
        url(
            r"cols/payments/monthly-confirmation-pdf/park-booking/(?P<id>\d+)",
            booking_views.MonthlyConfirmationPDFParkBookingView.as_view(),
            name="cols-monthly-confirmation-pdf-park",
        ),
        url(
            r"cols/payments/awaiting-payment-pdf/(?P<id>\d+)",
            booking_views.AwaitingPaymentInvoicePDFView.as_view(),
            name="cols-awaiting-payment-pdf",
        ),
        # following url is defined so that to include url path when sending Proposal amendment request to user.
        url(
            r"^external/proposal/(?P<proposal_pk>\d+)/$",
            views.ExternalProposalView.as_view(),
            name="external-proposal-detail",
        ),
        url(
            r"^internal/proposal/(?P<proposal_pk>\d+)/$",
            views.InternalProposalView.as_view(),
            name="internal-proposal-detail",
        ),
        url(
            r"^external/compliance/(?P<compliance_pk>\d+)/$",
            views.ExternalComplianceView.as_view(),
            name="external-compliance-detail",
        ),
        url(
            r"^internal/compliance/(?P<compliance_pk>\d+)/$",
            views.InternalComplianceView.as_view(),
            name="internal-compliance-detail",
        ),
        # filming
        url(
            r"^internal/proposal/(?P<proposal_pk>\d+)/district_proposal/(?P<district_proposal_pk>\d+)/$",
            views.DistrictProposalView.as_view(),
            name="internal-district-proposal-detail",
        ),
        # reversion history-compare
        url(
            r"^history/proposal/(?P<pk>\d+)/$",
            proposal_views.ProposalHistoryCompareView.as_view(),
            name="proposal_history",
        ),
        url(
            r"^history/filtered/(?P<pk>\d+)/$",
            proposal_views.ProposalFilteredHistoryCompareView.as_view(),
            name="proposal_filtered_history",
        ),
        url(
            r"^history/referral/(?P<pk>\d+)/$",
            proposal_views.ReferralHistoryCompareView.as_view(),
            name="referral_history",
        ),
        url(
            r"^history/approval/(?P<pk>\d+)/$",
            proposal_views.ApprovalHistoryCompareView.as_view(),
            name="approval_history",
        ),
        url(
            r"^history/compliance/(?P<pk>\d+)/$",
            proposal_views.ComplianceHistoryCompareView.as_view(),
            name="compliance_history",
        ),
        url(
            r"^history/proposaltype/(?P<pk>\d+)/$",
            proposal_views.ProposalTypeHistoryCompareView.as_view(),
            name="proposaltype_history",
        ),
        url(
            r"^history/organisation/(?P<pk>\d+)/$",
            organisation_views.OrganisationHistoryCompareView.as_view(),
            name="organisation_history",
        ),
        url(
            r"^ledger-ui/organisation/(?P<pk>[0-9]+)/",
            organisation_views.OrganisationDetailView.as_view(),
            name="view-organisation",
        ),
        url(
            r"^booking-session/abort-redirect$",
            booking_views.SessionAbortRedirectView.as_view(),
            name="booking-session-abort-redirect",
        ),
        url(r"^private-media/", views.getPrivateFile, name="view_private_file"),
        url(
            r"^email-exports/$", views.EmailExportsView.as_view(), name="email-exports"
        ),
    ]
    + ledger_patterns
    + media_serv_patterns
)


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.SHOW_DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns = [
        url("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
