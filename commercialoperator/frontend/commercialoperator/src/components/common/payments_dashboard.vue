<template id="proposal_dashboard">
    <div id="paymentDash" class="container">
        <div v-if="is_external && overdue_invoices.length > 0" class="row mb-3">
            <div class="col-sm-12 mb-2">
                <div class="card">
                    <div class="card-header">
                        <i
                            class="bi bi-exclamation-circle-fill text-danger me-2"
                        ></i>
                        The following invoice(s) are overdue:
                    </div>
                    <div class="card-body p-2">
                        <div class="card-text w-50">
                            <ul class="list-group d-inline-block">
                                <li
                                    v-for="invoice in overdue_invoices"
                                    :key="invoice.id"
                                    class="list-group-item list-group-item-danger m-2"
                                >
                                    {{ invoice.invoice_reference }}
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mb-3">
            <div class="col-sm-12">
                <div v-if="is_external" class="card mb-2">
                    <div class="card-header">Park Entry Fees</div>
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
            </div>
        </div>
        <div class="row mb-3">
            <div class="col-sm-12">
                <FormSection
                    :form-collapse="false"
                    label="Park Entry Fees"
                    index="park_entry_fees"
                    subtitle=""
                >
                    <div class="row mb-1">
                        <div class="col-md-2">
                            <div
                                id="select_park_entry_fees_parks_parent"
                                class="form-group"
                            >
                                <label for="select_park_entry_fees_parks"
                                    >Park</label
                                >
                                <select
                                    id="select_park_entry_fees_parks"
                                    ref="select_park_entry_fees_parks"
                                    v-model="filterProposalPark"
                                    class="form-select"
                                >
                                    <option value="All">All</option>
                                    <option
                                        v-for="s in parks"
                                        :key="s.value"
                                        :value="s.value"
                                    >
                                        {{ s.name }}
                                    </option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-2">
                            <div
                                id="select_park_entry_fees_status_parent"
                                class="form-group"
                            >
                                <label for="select_park_entry_fees_status"
                                    >Status</label
                                >
                                <select
                                    id="select_park_entry_fees_status"
                                    ref="select_park_entry_fees_status"
                                    v-model="filterProposalStatus"
                                    class="form-select"
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
                        <div class="col-md-2">
                            <div
                                id="select_park_entry_fees_payment_method_parent"
                                class="form-group"
                            >
                                <label
                                    for="select_park_entry_fees_payment_method"
                                    >Payment Method</label
                                >
                                <select
                                    id="select_park_entry_fees_payment_method"
                                    ref="select_park_entry_fees_payment_method"
                                    v-model="filterProposalPaymentMethod"
                                    class="form-select"
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

                        <div class="col-md-3">
                            <div class="form-group">
                                <label for="input_proposal_lodged_from"
                                    >Arrival From</label
                                >
                                <div
                                    ref="proposalDateFromPicker"
                                    class="input-group date"
                                >
                                    <input
                                        id="input_proposal_lodged_from"
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
                                <label for="input_proposal_lodged_to"
                                    >Arrival To</label
                                >
                                <div
                                    ref="proposalDateToPicker"
                                    class="input-group date"
                                >
                                    <input
                                        id="input_proposal_lodged_to"
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

                    <div class="row mb-3 justify-content-end">
                        <div v-if="is_external" class="col-md-3">
                            <div class="form-group mt-auto mb-0 align-self-end">
                                <router-link
                                    type="button"
                                    class="btn btn-primary float-end"
                                    :to="{ name: 'external-payment_order' }"
                                    >Make Payment</router-link
                                >
                            </div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-lg-12" style="margin-top: 25px">
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
import _ from 'lodash';
import $ from 'jquery';
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
            parks: [],
            proposal_headers: [
                'Number',
                'Licence',
                'Holder',
                'Trading name',
                'Status',
                'Payment Method',
                'Arrival',
                'Park',
                'Visitors',
                'Invoice/Confirmation',
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
                order: [[0, 'desc']],
                lengthMenu: [
                    [10, 25, 50, 100],
                    [10, 25, 50, 100],
                ],
                ajax: {
                    url: api_endpoints.booking_paginated_internal,
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
                        name: 'admission_number',
                        searchable: true,
                        orderable: true,
                    },
                    {
                        data: 'approval_number',
                        name: 'proposal__approval__lodgement_number',
                        searchable: true,
                        orderable: true,
                    },
                    {
                        data: 'applicant',
                        name: 'proposal__approval__org_applicant__organisation__organisation_name, proposal__approval__proxy_applicant__first_name, proposal__approval__proxy_applicant__last_name, proposal__approval__proxy_applicant__email',
                        orderable: false,
                        searchable: false,
                        visible: this.level == 'internal' ? true : false,
                    },
                    {
                        data: 'trading_name',
                        name: 'proposal__org_applicant__organisation__organisation_trading_name, proposal__org_applicant__organisation__organisation_name',
                        orderable: false,
                        searchable: false,
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
                        data: 'park_bookings',
                        // eslint-disable-next-line no-unused-vars
                        mRender: function (data, type, full) {
                            let arrival_dates = '';
                            _.forEach(data, function (park) {
                                arrival_dates +=
                                    (park.arrival != '' && park.arrival != null
                                        ? moment(park.arrival).format(
                                              vm.dateFormat
                                          )
                                        : '') + '<br>';
                            });
                            return arrival_dates;
                        },
                        name: 'park_bookings__arrival',
                        searchable: false,
                        orderable: true,
                    },
                    {
                        data: 'park_bookings',
                        // eslint-disable-next-line no-unused-vars
                        mRender: function (data, type, full) {
                            let parks = '';
                            _.forEach(data, function (item) {
                                parks += item.park + '<br>';
                            });
                            return parks;
                        },
                        name: 'park_bookings__park__name',
                        searchable: true,
                    },
                    {
                        data: 'park_bookings',
                        // eslint-disable-next-line no-unused-vars
                        mRender: function (data, type, full) {
                            let visitors = '';
                            _.forEach(data, function (item) {
                                visitors +=
                                    'A: ' +
                                    item.no_adults +
                                    '; C: ' +
                                    item.no_children +
                                    '; F: ' +
                                    item.no_free_of_charge +
                                    '<br>';
                            });
                            return visitors;
                        },
                        searchable: false,
                        orderable: false,
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
                                links += `<a href='/cols/payments/invoice-pdf/${full.invoice_reference}.pdf' target='_blank'><i style='color:red;' class='fas fa-file-pdf'></i></a>&nbsp;`;
                                links += `<a href='/cols/payments/confirmation-pdf/${full.invoice_reference}.pdf' target='_blank'><i style='color:red;' class='fas fa-file-pdf'></i></a><br/>`;
                            } else if (
                                full.payment_method.toLowerCase() ==
                                    'monthly invoicing' &&
                                full.invoice_reference == null
                            ) {
                                // running aggregated monthly booking - not yet invoiced
                                links += `<a href='/cols/payments/monthly-confirmation-pdf/booking/${full.id}.pdf' target='_blank' style='padding-left: 52px;'><i style='color:red;' class='fas fa-file-pdf'></i></a><br/>`;
                            }
                            return links;
                        },
                        name: '',
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
                                    links += `<a href='/cols/payments/invoice-payment-view/${full.invoice_reference}' target='_blank'>View Payment</a><br/>`;
                                } else if (
                                    full.payment_method.toLowerCase() ==
                                    'invoice not found'
                                ) {
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
            //this.$refs.proposal_datatable.vmDataTable.draw();
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
                    .columns(4)
                    .search(vm.filterProposalStatus)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(4)
                    .search('')
                    .draw();
            }
        },
        filterProposalPaymentMethod: function () {
            let vm = this;
            if (vm.filterProposalPaymentMethod != 'All') {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(4)
                    .search(vm.filterProposalPaymentMethod)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(4)
                    .search('')
                    .draw();
            }
        },
        filterProposalPark: function () {
            let vm = this;

            if (vm.filterProposalPark && vm.filterProposalPark !== 'All') {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(6)
                    .search(vm.filterProposalPark)
                    .draw();
            } else {
                vm.$refs.proposal_datatable.vmDataTable
                    .columns(6)
                    .search('')
                    .draw();
            }
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
        this.fetchParkLists();
        let vm = this;
        $('a[data-bs-toggle="collapse"]').on('click', function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass('fa-chevron-down fa-chevron-up');
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

            // Internal Extend listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-extend-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-extend-approval');
                    vm.extendApproval(id);
                }
            );

            //Internal Cancel listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-cancel-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-cancel-approval');
                    vm.cancelApproval(id);
                }
            );

            //Internal Suspend listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-suspend-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-suspend-approval');
                    vm.suspendApproval(id);
                }
            );

            // Internal Reinstate listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-reinstate-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-reinstate-approval');
                    vm.reinstateApproval(id);
                }
            );

            //Internal/ External Surrender listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-surrender-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-surrender-approval');
                    vm.surrenderApproval(id);
                }
            );

            // External renewal listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-renew-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-renew-approval');
                    vm.renewApproval(id);
                }
            );

            // External amend listener
            vm.$refs.proposal_datatable.vmDataTable.on(
                'click',
                'a[data-amend-approval]',
                function (e) {
                    e.preventDefault();
                    var id = $(this).attr('data-amend-approval');
                    vm.amendApproval(id);
                }
            );

            helpers.initialiseSelect2.bind(this)(
                'select_park_entry_fees_parks',
                'select_park_entry_fees_parks_parent',
                'filterProposalPark',
                'Select Park',
                false
            );
            helpers.initialiseSelect2.bind(this)(
                'select_park_entry_fees_status',
                'select_park_entry_fees_status_parent',
                'filterProposalStatus',
                'Select Status',
                false
            );
            helpers.initialiseSelect2.bind(this)(
                'select_park_entry_fees_payment_method',
                'select_park_entry_fees_payment_method_parent',
                'filterProposalPaymentMethod',
                'Select Payment Method',
                false
            );
        },
        fetchParkLists() {
            let vm = this;
            vm.parks = [];

            // Show "Loading..." inside the Select2 dropdown while fetching
            vm.$nextTick(() => {
                const $select = $('#select_park_entry_fees_parks');
                if ($select.data('select2')) {
                    $select.select2('destroy');
                }
                $select.select2({
                    placeholder: 'Loading...',
                    allowClear: false,
                });
                $select.prop('disabled', true);
            });

            helpers
                .fetchUrl(api_endpoints.parks_all)
                .then((response) => {
                    let parksArray = [];

                    if (Array.isArray(response)) {
                        parksArray = response;
                    } else if (response && Array.isArray(response.data)) {
                        parksArray = response.data;
                    } else {
                        console.warn('Unexpected response format:', response);
                        parksArray = [];
                    }

                    vm.parks = parksArray.map((park) => ({
                        name: park.name,
                        value: park.id,
                    }));
                })
                .catch((error) => {
                    console.error('Error fetching parks:', error);
                })
                .finally(() => {
                    vm.$nextTick(() => {
                        // Re-init Select2 with same args as the other dropdowns
                        helpers.initialiseSelect2.bind(vm)(
                            'select_park_entry_fees_parks',
                            'select_park_entry_fees_parks_parent',
                            'filterProposalPark',
                            'Select Park',
                            false
                        );
                        $('#select_park_entry_fees_parks').prop(
                            'disabled',
                            false
                        );
                    });
                });
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
