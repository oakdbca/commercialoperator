<template id="proposal_dashboard">
    <div id="paymentDash" class="container">
        <div
            v-if="is_external && overdue_invoices.length > 0"
            class="row error"
        >
            <div class="col-sm-12 mb-2">
                <div class="card">
                    <div class="card-header">
                        The following invoice(s) are overdue:
                    </div>
                    <div class="card-body bg-light p-2">
                        <div class="card-text">
                            <div
                                v-for="invoice in overdue_invoices"
                                :key="invoice.id"
                            >
                                {{ invoice.invoice_reference }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-sm-12">
                <div v-if="is_external" class="card mb-2">
                    <div class="card-header">Park Entry Fees (per Park)</div>
                    <div class="card-body">
                        <p class="card-text">
                            Entry fees apply to passenger
                            <a :href="payment_help_url" target="_blank"
                                ><i
                                    class="fas fa-circle-question"
                                    style="color: blue"
                                    >&nbsp;</i
                                ></a
                            >
                        </p>
                    </div>
                </div>
                    <FormSection
                        :form-collapse="false"
                        label="Park Entry Fees (per Park)"
                        index="parl_entry_fees_per_park"
                        subtitle=""
                    >
                        <div class="row mb-1">
                            <div class="col-md-3">
                                <div
                                    id="select_parkbooking_status_parent"
                                    class="form-group"
                                >
                                    <label for="select_parkbooking_status"
                                        >Status</label
                                    >
                                    <select
                                        id="select_parkbookings_status"
                                        ref="select_parkbookings_status"
                                        v-model="filterProposalStatus"
                                        class="form-control"
                                    >
                                        <option value="All">All</option>
                                        <option
                                            v-for="s in payment_status"
                                            :key="s.value"
                                            :value="s.value"
                                        >
                                            {{ s.name }}
                                        </option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div
                                    id="select_parkbookings_payment_method_parent"
                                    class="form-group"
                                >
                                    <label
                                        for="select_parkbookings_payment_method"
                                        >Payment Method</label
                                    >
                                    <select
                                        id="select_parkbookings_payment_method"
                                        ref="select_parkbookings_payment_method"
                                        v-model="filterProposalPaymentMethod"
                                        class="form-control"
                                    >
                                        <option value="All">All</option>
                                        <option
                                            v-for="s in payment_method"
                                            :key="s.value"
                                            :value="s.value"
                                        >
                                            {{ s.name }}
                                        </option>
                                    </select>
                                </div>
                            </div>
                            <div v-if="is_external" class="col-md-3">
                                <div class="form-group">
                                    <router-link
                                        style="margin-top: 25px"
                                        class="btn btn-primary pull-right"
                                        :to="{ name: 'external-payment_order' }"
                                        >Make Payment</router-link
                                    >
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="form-group">
                                    <label for="input_parkbookings_arrival_to"
                                        >Arrival From</label
                                    >
                                    <div
                                        ref="proposalDateFromPicker"
                                        class="input-group date"
                                    >
                                        <input
                                            id="input_parkbookings_arrival_from"
                                            v-model="filterProposalLodgedFrom"
                                            type="date"
                                            class="form-control"
                                            max="2999-12-31"
                                            placeholder="DD/MM/YYYY"
                                        />
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="form-group">
                                    <label for="input_parkbookings_arrival_to"
                                        >Arrival To</label
                                    >
                                    <div
                                        ref="proposalDateToPicker"
                                        class="input-group date"
                                    >
                                        <input
                                            id="input_parkbookings_arrival_to"
                                            v-model="filterProposalLodgedTo"
                                            type="date"
                                            class="form-control"
                                            max="2999-12-31"
                                            placeholder="DD/MM/YYYY"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-lg-12">
                                <datatable
                                    :id="datatable_id"
                                    ref="proposal_datatable"
                                    :dt-options="proposal_options"
                                    :dt-headers="proposal_headers"
                                />
                            </div>
                        </div>
                    </FormSection>
            </div>
        </div>
    </div>
</template>
<script>
import FormSection from '@/components/forms/section_toggle.vue';
import datatable from '@/utils/vue/datatable.vue';
import { api_endpoints, constants, helpers } from '@/utils/hooks';
import { v4 as uuid } from 'uuid';
import $ from 'jquery'
export default {
    name: 'ProposalTableDash',
    components: {
        FormSection,
        datatable,
    },
    props: {
        level: {
            type: String,
            required: true,
            validator: function (val) {
                let options = ['internal', 'referral', 'external'];
                return options.indexOf(val) != -1 ? true : false;
            },
        },
    },
    data() {
        let vm = this;
        return {
            pBody: 'pBody' + uuid(),
            datatable_id: 'proposal-datatable-' + uuid(),
            //Profile to check if user has access to process Proposal
            profile: {},
            is_payment_admin: false,
            overdue_invoices: [],
            // Filters for Proposals
            filterProposalPark: 'All',
            filterProposalStatus: 'All',
            filterProposalPaymentMethod: 'All',
            filterProposalLodgedFrom: '',
            filterProposalLodgedTo: '',
            filterProposalSubmitter: 'All',
            dateFormat: 'DD/MM/YYYY',
            payment_status: [
                { name: 'Paid', value: 'paid' },
                { name: 'Over Paid', value: 'over_paid' },
                { name: 'Partially Paid', value: 'partially_paid' },
                { name: 'Unpaid', value: 'unpaid' },
                { name: 'Overdue', value: 'overdue' },
            ],
            payment_method: [
                { name: 'Credit Card', value: '0' },
                { name: 'BPAY', value: '1' },
                { name: 'Monthly Invoicing', value: '2' },
                { name: 'Other', value: '3' },
            ],
            proposal_headers: [
                'Number',
                'Licence',
                'Trading name',
                'Arrival',
                'Park',
                'Visitors',
                'Invoice/Confirmation',
                'Holder',
                'Status',
                'Payment Method',
                'Action',
            ],
            proposal_options: {
                language: {
                    processing: constants.DATATABLE_PROCESSING_HTML,
                },
                columnDefs: [
                    { responsivePriority: 1, targets: 0 },
                    {
                        responsivePriority: 2,
                        targets: -1,
                    },
                ],
                responsive: true,
                serverSide: true,
                lengthMenu: [
                    [10, 25, 50, 100],
                    [10, 25, 50, 100],
                ],
                ajax: {
                    url: api_endpoints.parkbooking_paginated_internal,
                    dataSrc: 'data',

                    // adding extra GET params for Custom filtering
                    data: function (d) {
                        d.park =
                            vm.filterProposalPark != 'All' &&
                            vm.filterProposalPark != null
                                ? vm.filterProposalPark
                                : '';
                        d.payment_status =
                            vm.filterProposalStatus != 'All' &&
                            vm.filterProposalStatus != null
                                ? vm.filterProposalStatus
                                : '';
                        d.payment_method =
                            vm.filterProposalPaymentMethod != 'All' &&
                            vm.filterProposalPaymentMethod != null
                                ? vm.filterProposalPaymentMethod
                                : '';
                        d.date_from =
                            vm.filterProposalLodgedFrom != '' &&
                            vm.filterProposalLodgedFrom != null
                                ? moment(vm.filterProposalLodgedFrom).format(
                                      'YYYY-MM-DD'
                                  )
                                : '';
                        d.date_to =
                            vm.filterProposalLodgedTo != '' &&
                            vm.filterProposalLodgedTo != null
                                ? moment(vm.filterProposalLodgedTo).format(
                                      'YYYY-MM-DD'
                                  )
                                : '';
                    },
                },
                dom: constants.DATATABLE_DOM_HTML,
                buttons: [
                    {
                        extend: 'excelHtml5',
                        text: 'Excel',
                        className: 'btn btn-primary me-2 rounded',
                        exportOptions: {
                            orthogonal: 'export',
                        },
                    },
                    {
                        extend: 'csvHtml5',
                        text: 'CSV',
                        className: 'btn btn-primary rounded',
                        exportOptions: {
                            orthogonal: 'export',
                        },
                    },
                ],
                columns: [
                    {
                        data: 'admission_number',
                        name: 'booking__admission_number',
                        searchable: true,
                        orderable: true,
                    },
                    {
                        data: 'approval_number',
                        name: 'booking__proposal__approval__lodgement_number',
                        searchable: true,
                        orderable: true,
                    },
                    {
                        data: 'trading_name',
                        name: 'booking__proposal__org_applicant__organisation__organisation_trading_name, booking__proposal__org_applicant__organisation__organisation_name',
                        searchable: false,
                        orderable: false,
                    },
                    {
                        data: 'arrival',
                        mRender: function (data, type, full) {
                            let arrival_dates = '';
                            arrival_dates +=
                                full.arrival != '' && full.arrival != null
                                    ? moment(full.arrival).format(vm.dateFormat)
                                    : '';
                            return arrival_dates;
                        },
                        name: 'arrival',
                        searchable: false,
                        orderable: true,
                    },
                    {
                        data: 'park',
                        name: 'park__name',
                        searchable: true,
                        orderable: true,
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            let visitors = '';
                            visitors +=
                                'A: ' +
                                full.no_adults +
                                '; C: ' +
                                full.no_children +
                                '; F: ' +
                                full.no_free_of_charge +
                                '<br>';
                            return visitors;
                        },
                        searchable: false,
                        orderable: true,
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            let links = '';
                            if (
                                full.payment_status.toLowerCase() == 'paid' ||
                                full.payment_method.toUpperCase() == 'BPAY' ||
                                (full.payment_method.toLowerCase() ==
                                    'monthly invoicing' &&
                                    full.invoice_reference !== null)
                            ) {
                                links += `<a href='/cols/payments/invoice-pdf/${full.invoice_reference}.pdf' target='_blank'><i style='color:red;' class='fas fa-file-pdf'></i></a> &nbsp`;
                                links += `<a href='/cols/payments/confirmation-pdf/${full.invoice_reference}.pdf' target='_blank'><i style='color:red;' class='fas fa-file-pdf'></i></a><br/>`;
                            } else if (
                                full.payment_method.toLowerCase() ==
                                    'monthly invoicing' &&
                                full.invoice_reference == null
                            ) {
                                // running aggregated monthly booking - not yet invoiced
                                links += `<a href='/cols/payments/monthly-confirmation-pdf/park-booking/${full.id}.pdf' target='_blank' style='padding-left: 52px;'><i style='color:red;' class='fas fa-file-pdf'></i></a><br/>`;
                            }
                            return links;
                        },
                        name: '',
                        searchable: false,
                        orderable: false,
                    },
                    {
                        data: 'applicant',
                        name: 'booking__proposal__approval__org_applicant__organisation__name, booking__proposal__approval__proxy_applicant__email, proposal__approval__proxy_applicant__first_name, booking__proposal__approval__proxy_applicant__last_name',
                        visible: this.level == 'internal' ? true : false,
                        searchable: false,
                        orderable: false,
                    },
                    {
                        data: 'payment_status',
                        name: 'payment_status',
                        searchable: false,
                        orderable: false,
                    },
                    {
                        data: 'payment_method',
                        name: 'payment_method',
                        searchable: false,
                        orderable: false,
                    },
                    {
                        data: 'id',
                        mRender: function (data, type, full) {
                            let links = '';
                            if (vm.is_payment_admin) {
                                if (
                                    full.payment_status.toLowerCase() ==
                                        'paid' ||
                                    full.payment_status.toLowerCase() ==
                                        'over_paid'
                                ) {
                                    links += `<a href='/cols/payments/invoice-payment-view/${full.fee_invoice_reference}' target='_blank'>View Payment</a><br/>`;
                                } else if (full.payment_method.toLowerCase() == 'invoice not found') {
                                    links += ``;
                                } else if (full.invoice_reference !== null) {
                                    links += `<a href='/cols/payments/invoice-payment-view/${full.invoice_reference}' target='_blank'>Record Payment</a><br/>`;
                                }
                            }
                            return links;
                        },
                        name: '',
                        searchable: false,
                        orderable: false,
                        visible: vm.level == 'internal' ? true : false,
                    },
                ],
                processing: true,
            },
        };
    },
    computed: {
        status: function () {
            //return this.is_external ? this.external_status : this.internal_status;
            return [];
        },
        is_external: function () {
            return this.level == 'external';
        },
        is_internal: function () {
            return this.level == 'internal';
        },
        payment_help_url: function () {
            return api_endpoints.payment_help_url;
        },
    },
    watch: {
        filterProposalSubmitter: function () {
            let vm = this;
            if (vm.filterProposalSubmitter != 'All') {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(2)
                    .search(vm.filterProposalSubmitter)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(2)
                    .search('')
                    .draw();
            }
        },
        filterProposalStatus: function () {
            let vm = this;
            if (vm.filterProposalStatus != 'All') {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(9)
                    .search(vm.filterProposalStatus)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(9)
                    .search('')
                    .draw();
            }
        },
        filterProposalPaymentMethod: function () {
            let vm = this;
            if (vm.filterProposalPaymentMethod != 'All') {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(10)
                    .search(vm.filterProposalPaymentMethod)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(10)
                    .search('')
                    .draw();
            }
        },
        filterProposalPark: function () {
            let vm = this;
            vm.$refs.proposal_datatable.vmDataTable
                .columns(4)
                .search('')
                .draw();
        },

        filterProposalLodgedFrom: function () {
            this.$refs.proposal_datatable.vmDataTable.ajax.reload(
                helpers.enablePopovers,
                false
            );
        },
        filterProposalLodgedTo: function () {
            this.$refs.proposal_datatable.vmDataTable.ajax.reload(
                helpers.enablePopovers,
                false
            );
        },
    },
    mounted: function () {
        this.fetchOverdueInvoices();
        this.fetchProfile();
        let vm = this;
        $('a[data-bs-toggle="collapse"]').on('click', function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass(
                    'fa-chevron-down fa-chevron-up'
                );
            }, 100);
        });
        this.$nextTick(() => {
            vm.addEventListeners();
            vm.initialiseSearch();
        });
    },
    methods: {
        fetchOverdueInvoices: function () {
            let vm = this;

            helpers.fetchUrl(api_endpoints.overdue_invoices).then(
                (response) => {
                    vm.overdue_invoices = response.results;
                },
                (error) => {
                    console.log(error);
                }
            );
        },

        addEventListeners: function () {
            let vm = this;
            // Internal Reissue listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-reissue-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-reissue-approval');
                    vm.reissueApproval(id);
                }
            );

            helpers.initialiseSelect2.bind(this)(
                'select_parkbookings_park',
                'select_parkbookings_park_parent',
                'filterProposalPark',
                'Select a Park',
                false
            );
            helpers.initialiseSelect2.bind(this)(
                'select_parkbookings_status',
                'select_parkbooking_status_parent',
                'filterProposalStatus',
                'Select a Status',
                false
            );
            helpers.initialiseSelect2.bind(this)(
                'select_parkbookings_payment_method',
                'select_parkbookings_payment_method_parent',
                'filterProposalPaymentMethod',
                'Select a Payment Method',
                false
            );
        },
        initialiseSearch: function () {
            this.dateSearch();
        },
        submitterSearch: function () {
            let vm = this;
            vm.$refs.proposal_datatable.table.dataTableExt.afnFiltering.push(
                function (settings, data, dataIndex, original) {
                    let filtered_submitter = vm.filterProposalSubmitter;
                    if (filtered_submitter == 'All') {
                        return true;
                    }
                    return filtered_submitter == original.submitter.email;
                }
            );
        },
        dateSearch: function () {
            let vm = this;
            vm.$refs.proposal_datatable.table.dataTableExt.afnFiltering.push(
                function (settings, data, dataIndex, original) {
                    let from = vm.filterProposalLodgedFrom;
                    let to = vm.filterProposalLodgedTo;
                    let val = original.expiry_date;

                    if (from == '' && to == '') {
                        return true;
                    } else if (from != '' && to != '') {
                        return val != null && val != ''
                            ? moment()
                                  .range(
                                      moment(from, vm.dateFormat),
                                      moment(to, vm.dateFormat)
                                  )
                                  .contains(moment(val))
                            : false;
                    } else if (from == '' && to != '') {
                        if (val != null && val != '') {
                            return moment(to, vm.dateFormat).diff(
                                moment(val)
                            ) >= 0
                                ? true
                                : false;
                        } else {
                            return false;
                        }
                    } else if (to == '' && from != '') {
                        if (val != null && val != '') {
                            return moment(val).diff(
                                moment(from, vm.dateFormat)
                            ) >= 0
                                ? true
                                : false;
                        } else {
                            return false;
                        }
                    } else {
                        return false;
                    }
                }
            );
        },

        fetchProfile: function () {
            let vm = this;
            helpers.fetchUrl(api_endpoints.profile).then(
                (response) => {
                    vm.profile = response;
                    vm.is_payment_admin = response.is_payment_admin;
                },
                (error) => {
                    console.log(error);
                }
            );
        },

        refreshFromResponse: function () {
            this.$refs.proposal_datatable.vmDataTable.ajax.reload();
        },
    },
};
</script>
<style scoped>
.error {
    color: red;
}
</style>
