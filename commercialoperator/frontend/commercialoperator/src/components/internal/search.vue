<template>
    <div id="internalSearch" class="container">
        <div class="row mb-3">
            <div class="col-sm-12">
                <FormSection
                    :form-collapse="false"
                    label="Search Organisation"
                    index="search_organisation"
                >
                    <div class="row my-3">
                        <form name="searchOrganisationForm">
                            <div class="col-md-6">
                                <div class="input-group">
                                    <TextFilteredOrgField
                                        id="id_org"
                                        class="flex-grow-1"
                                        :url="filtered_org_url"
                                        name="Organisation"
                                    />
                                    <button
                                        type="button"
                                        class="btn btn-primary"
                                        @click.prevent="viewOrgDetails"
                                    >
                                        View Details
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </FormSection>
            </div>
        </div>
        <div class="row mb-3">
            <div class="col-sm-12">
                <FormSection
                    :form-collapse="false"
                    label="Search User"
                    index="search_user"
                >
                    <div class="row my-3">
                        <form name="searchUserForm">
                            <div class="col-md-6">
                                <div class="input-group">
                                    <TextFilteredField
                                        id="id_holder"
                                        class="flex-grow-1"
                                        :url="filtered_url"
                                        name="User"
                                    />
                                    <button
                                        type="button"
                                        class="btn btn-primary"
                                        @click.prevent="viewUserDetails"
                                    >
                                        View Details
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </FormSection>
            </div>
        </div>
        <div class="row mb-3">
            <div class="col-sm-12">
                <FormSection
                    :form-collapse="false"
                    label="Search Keywords"
                    index="search-keywords"
                >
                    <div class="row">
                        <div class="col-lg-12">
                            <div class="mb-3">
                                <label
                                    for=""
                                    class="col-form-label col-lg-12 fs-5"
                                    >Record Types to Search</label
                                >
                                <div class="form-check col">
                                    <input
                                        id="searchProposal"
                                        ref="searchProposal"
                                        v-model="searchProposal"
                                        class="form-check-input"
                                        name="searchProposal"
                                        type="checkbox"
                                    />
                                    <label
                                        class="form-check-label fw-normal"
                                        for="searchProposal"
                                        >Application</label
                                    >
                                </div>
                                <div class="form-check col">
                                    <input
                                        id="searchApproval"
                                        ref="searchApproval"
                                        v-model="searchApproval"
                                        class="form-check-input"
                                        name="searchApproval"
                                        type="checkbox"
                                    />
                                    <label
                                        class="form-check-label fw-normal"
                                        for="searchApproval"
                                        >License</label
                                    >
                                </div>
                                <div class="form-check col">
                                    <input
                                        id="searchCompliance"
                                        ref="searchCompliance"
                                        v-model="searchCompliance"
                                        class="form-check-input"
                                        name="searchCompliance"
                                        type="checkbox"
                                    />
                                    <label
                                        class="form-check-label fw-normal"
                                        for="searchCompliance"
                                        >Compliance with requirements</label
                                    >
                                </div>

                                <label
                                    for=""
                                    class="col-form-label col-lg-12 fs-5"
                                    >Keyword(s)</label
                                >
                                <div class="row">
                                    <div class="col-md-4">
                                        <div class="input-group">
                                            <input
                                                ref="keyWord"
                                                v-model="keyWord"
                                                type="search"
                                                class="form-control"
                                                name="details"
                                                placeholder=""
                                                @keyup.enter="add"
                                            />
                                            <button
                                                type="button"
                                                class="btn btn-primary"
                                                @click.prevent="add"
                                            >
                                                <i
                                                    class="bi bi-plus-lg me-2"
                                                ></i
                                                >Add Keyword
                                            </button>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div>
                                            <button
                                                v-if="searching"
                                                type="button"
                                                class="btn btn-primary btn-margin me-3"
                                                value="Search"
                                                disabled
                                            >
                                                <i class="bi bi-search me-2"></i
                                                >Search<i
                                                    class="fa fa-circle-o-notch fa-spin fa-fw ms-2"
                                                ></i>
                                            </button>
                                            <button
                                                v-else
                                                type="button"
                                                class="btn btn-primary btn-margin me-3"
                                                value="Search"
                                                :disabled="
                                                    !searchKeywords ||
                                                    searchKeywords.length === 0
                                                "
                                                @click.prevent="search"
                                            >
                                                <i class="bi bi-search me-2"></i
                                                >Search
                                            </button>
                                            <button
                                                type="reset"
                                                class="btn btn-primary"
                                                value="Clear"
                                                :disabled="
                                                    !searchKeywords ||
                                                    searchKeywords.length === 0
                                                "
                                                @click.prevent="reset"
                                            >
                                                <i class="bi bi-x me-2"></i
                                                >Clear All Keywords
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Keyword Tags -->
                    <div class="row mb-1">
                        <div class="col-lg-12">
                            <ul class="list-inline">
                                <li
                                    v-for="(item, i) in searchKeywords"
                                    :key="i"
                                    class="list-inline-item"
                                >
                                    <button
                                        class="btn btn-light border"
                                        @click.prevent=""
                                    >
                                        {{ item }}
                                        <a
                                            href=""
                                            @click.prevent="removeKeyword(i)"
                                        >
                                            <span class="bi bi-x ps-2"></span>
                                        </a>
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <!-- Preserved Alert Component -->
                    <div v-if="showMessage" class="row my-2">
                        <div class="col-lg-12">
                            <alert type="danger">
                                <strong>
                                    <!-- eslint-disable-next-line vue/no-v-html -->
                                    <p class="mb-0" v-html="messageString"></p>
                                </strong>
                            </alert>
                        </div>
                    </div>

                    <!-- Datatable -->
                    <div class="row">
                        <div class="col-lg-12">
                            <datatable
                                :id="datatable_id"
                                ref="proposal_datatable"
                                class="border rounded p-2"
                                :dt-options="proposal_options"
                                :dt-headers="proposal_headers"
                            />
                        </div>
                    </div>
                </FormSection>
            </div>
        </div>
        <div class="row">
            <div class="col-sm-12">
                <FormSection
                    :form-collapse="false"
                    label="Search Reference Number"
                    index="reference"
                >
                    <div class="row mb-1">
                        <div class="row">
                            <div class="col-md-4">
                                <div class="input-group">
                                    <input
                                        ref="referenceWord"
                                        v-model="referenceWord"
                                        type="search"
                                        class="form-control input-sm"
                                        name="referenceWord"
                                        placeholder="reference number"
                                        required
                                        @input="resetError"
                                    />
                                    <input
                                        type="button"
                                        class="btn btn-primary"
                                        value="Search"
                                        @click.prevent="
                                            search_reference(
                                                $refs.referenceWord
                                            )
                                        "
                                    />
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <alert v-if="showError" type="danger"
                                ><strong>{{ errorString }}</strong></alert
                            >
                        </div>
                    </div>
                </FormSection>

                <!-- <FormSection
                    :form-collapse="false"
                    label="Reference"
                    index="reference"
                >
                    <div class="row">
                        <label
                            for="input_search_reference"
                            class="control-label col-lg-12"
                            >Reference</label
                        >
                        <div class="col-md-8">
                            <input
                                id="input_search_reference"
                                v-model="referenceWord"
                                type="search"
                                class="form-control input-sm"
                                name="referenceWord"
                                placeholder=""
                            />
                        </div>
                        <div>
                            <input
                                type="button"
                                class="btn btn-primary"
                                style="margin-bottom: 5px"
                                value="Search"
                                @click.prevent="search_reference"
                            />
                        </div>
                        <alert v-if="showError" type="danger"
                            ><strong>{{ errorString }}</strong></alert
                        >
                    </div>
                </FormSection> -->
            </div>
        </div>
    </div>
</template>
<script>
import $ from 'jquery';
import datatable from '@/utils/vue/datatable.vue';
import alert from '@vue-utils/alert.vue';
import FormSection from '@/components/forms/section_toggle.vue';
import TextFilteredField from '@/components/forms/text-filtered.vue';
import TextFilteredOrgField from '@/components/forms/text-filtered-org.vue';
import { api_endpoints, constants, helpers } from '@/utils/hooks';
import { v4 as uuid } from 'uuid';

export default {
    name: 'ExternalDashboard',
    components: {
        alert,
        FormSection,
        datatable,
        TextFilteredField,
        TextFilteredOrgField,
    },
    props: {
        proposalSearchKeywordsUrl: {
            type: String,
            default: api_endpoints.proposal_search_keywords,
        },
    },
    data() {
        let vm = this;
        return {
            rBody: 'rBody' + uuid(),
            oBody: 'oBody' + uuid(),
            uBody: 'uBody' + uuid(),
            kBody: 'kBody' + uuid(),
            loading: [],
            searching: false,
            filtered_url: api_endpoints.filtered_users + '?search=',
            filtered_org_url: api_endpoints.filtered_organisations + '?search=',
            user_id: null,
            searchKeywords: [],
            searchProposal: true,
            searchApproval: false,
            searchCompliance: false,
            referenceWord: '',
            keyWord: null,
            selected_organisation: '',
            organisations: null,
            results: [],
            hasErrors: false,
            errorString: '',
            messages: false,
            messageString: '',
            datatable_id: 'proposal-datatable-' + uuid(),
            proposal_headers: [
                'Number',
                'Type',
                'Proponent',
                'Text found',
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
                ajax: {
                    url: vm.proposalSearchKeywordsUrl,
                    dataSrc: 'data',
                    data: function (d) {
                        d.searchKeywords = JSON.stringify(vm.searchKeywords);
                        d.searchProposal = vm.searchProposal;
                        d.searchApproval = vm.searchApproval;
                        d.searchCompliance = vm.searchCompliance;
                        d.is_internal = true;
                    },
                },
                order: [[0, 'desc']],
                pageLength: 10,
                columns: [
                    { data: 'number', name: 'lodgement_number' },
                    // NOTE: Changing all columns below to be neither searchable nor orderable, b/c this table's dataset consists of thee different models
                    { data: 'type', searchable: false, orderable: false },
                    { data: 'applicant', searchable: false, orderable: false },
                    {
                        data: 'text',
                        searchable: false,
                        orderable: false,
                        // eslint-disable-next-line no-unused-vars
                        mRender: function (data, type, full) {
                            if (data.value) {
                                return data.value;
                            } else {
                                return data;
                            }
                        },
                    },
                    {
                        data: 'id',
                        searchable: false,
                        orderable: false,
                        mRender: function (data, type, full) {
                            let links = '';
                            if (
                                full.type == 'Proposal' ||
                                full.type == 'Application'
                            ) {
                                links += `<a href='/internal/proposal/${full.id}'>View</a><br/>`;
                            }
                            if (full.type == 'Compliance') {
                                links += `<a href='/internal/compliance/${full.id}'>View</a><br/>`;
                            }
                            if (
                                full.type == 'Approval' ||
                                full.type == 'Licence'
                            ) {
                                links += `<a href='/internal/approval/${full.id}'>View</a><br/>`;
                            }
                            return links;
                        },
                    },
                ],
                processing: true,
            },
        };
    },
    computed: {
        showError: function () {
            var vm = this;
            return vm.hasErrors;
        },
        showMessage: function () {
            var vm = this;
            return vm.messages;
        },
    },
    watch: {},
    mounted: function () {
        $('a[data-bs-toggle="collapse"]').on('click', function () {
            var chev = $(this).children()[0];
            window.setTimeout(function () {
                $(chev).toggleClass('fa-chevron-down fa-chevron-up');
            }, 100);
        });
    },
    updated: function () {
        let vm = this;
        this.$nextTick(() => {
            vm.addListeners();
        });
    },
    methods: {
        addListeners: function () {
            let vm = this;
            // Initialise select2 for region
            $(vm.$refs.searchOrg)
                .select2({
                    theme: 'bootstrap-5',
                    allowClear: true,
                    placeholder: 'Select Organisation',
                })
                .on('select2:select', function (e) {
                    var selected = $(e.currentTarget);
                    vm.selected_organisation = selected.val();
                })
                .on('select2:unselect', function (e) {
                    var selected = $(e.currentTarget);
                    vm.selected_organisation = selected.val();
                });
        },
        viewOrgDetails: function () {
            let form = document.forms.searchOrganisationForm;
            const org_selected = form.elements['Organisation-selected'];
            const ledger_selected =
                form.elements['Organisation-selected-ledger'];
            const org_id =
                (ledger_selected && ledger_selected.value) ||
                (org_selected && org_selected.value);
            if (org_id) {
                window.location.href = `/ledger-ui/organisation/${org_id}`;
            } else {
                swal.fire({
                    title: 'Organisation not selected',
                    html: 'Please select the organisation to view the details',
                    icon: 'error',
                }).then(() => {});
                return;
            }
        },
        viewUserDetails: function () {
            let vm = this;
            let form = document.forms.searchUserForm;
            var user_selected = form.elements['User-selected'];
            if (user_selected != undefined || user_selected != null) {
                var user_id = user_selected.value;
                vm.$router.push({
                    name: 'internal-user-detail',
                    params: { user_id: user_id },
                });
            } else {
                swal.fire({
                    title: 'User not selected',
                    html: 'Please select the user to view the details',
                    icon: 'error',
                }).then(() => {});
                return;
            }
        },

        add: function () {
            let vm = this;
            const typedKeyword = (vm.keyWord || '').trim();
            if (typedKeyword && !vm.searchKeywords.includes(typedKeyword)) {
                vm.searchKeywords.push(typedKeyword);
            }
            vm.keyWord = '';
        },
        removeKeyword: function (index) {
            let vm = this;
            if (index > -1) {
                vm.searchKeywords.splice(index, 1);
            }
        },
        reset: function () {
            let vm = this;
            vm.searchKeywords = [];
            vm.keyWord = null;
            vm.results = [];
            vm.messages = false;
            vm.messageString = '';
            vm.$refs.proposal_datatable.vmDataTable.clear();
            vm.$refs.proposal_datatable.vmDataTable.search('');
            vm.$refs.proposal_datatable.vmDataTable.draw();
        },

        search: function () {
            let vm = this;
            console.log('Calling search');
            vm.$refs.proposal_datatable.vmDataTable.clear();
            if (vm.searchKeywords.length == 0 && vm.keyWord) {
                vm.searchKeywords.push(vm.keyWord);
            }
            vm.keyWord = '';
            vm.$refs.proposal_datatable.vmDataTable.draw();

            return;
        },

        search_reference: function () {
            let vm = this;
            console.log('Calling search_reference');
            const referenceWord = (vm.referenceWord || '').trim();
            if (referenceWord) {
                helpers
                    .fetchUrl(
                        '/api/search_reference.json?reference_number=' +
                            encodeURIComponent(referenceWord)
                    )
                    .then(
                        (res) => {
                            console.log(res);
                            const payload = res && res.body ? res.body : res;
                            vm.hasErrors = false;
                            vm.errorString = '';
                            if (payload && payload.type && payload.id) {
                                vm.$router.push({
                                    path:
                                        '/internal/' +
                                        payload.type +
                                        '/' +
                                        payload.id,
                                });
                            } else {
                                vm.hasErrors = true;
                                vm.errorString =
                                    'Unexpected search response format';
                            }
                        },
                        (error) => {
                            console.log(error);
                            vm.hasErrors = true;
                            vm.errorString = helpers.apiVueResourceError(error);
                        }
                    );
            }
        },
    },
};
</script>

<style scoped>
/* 1. Force the root wrapper and its internal form-group to grow */
.input-group > .flex-grow-1 {
    flex: 1 1 0% !important;
    min-width: 0 !important;
}

.input-group > .flex-grow-1 .form-group {
    margin-bottom: 0;
    width: 100%;
}

/* 2. Force v-select to take 100% of the space */
.input-group :deep(.organisation-search),
.input-group :deep(.v-select) {
    width: 100% !important;
}

/* 3. Style v-select toggle to seamlessly attach to the button */
.input-group :deep(.vs__dropdown-toggle) {
    min-height: 38px;
    background-color: #fff;
    border-top-right-radius: 0 !important;
    border-bottom-right-radius: 0 !important;
}

/* 4. Button radius and height matching */
.input-group > .btn {
    border-top-left-radius: 0 !important;
    border-bottom-left-radius: 0 !important;
    white-space: nowrap;
}

/* 1. Placeholder text */
:deep(.v-select .vs__search::placeholder) {
    color: var(--bs-secondary-color, #6c757d) !important;
}

/* 2. User input / typed text */
:deep(.v-select .vs__search) {
    color: var(--bs-body-color, #212529) !important;
}

/* 3. Selected option text */
:deep(.v-select .vs__selected) {
    color: var(--bs-body-color, #212529) !important;
}

/* 4. Dropdown options text */
:deep(.v-select .vs__dropdown-option) {
    color: var(--bs-body-color, #212529) !important;
}

/* 5. Dropdown option hover/highlight text & background (BS5 style) */
:deep(.v-select .vs__dropdown-option--highlight) {
    background: var(--bs-primary, #0d6efd) !important;
    color: #fff !important;
}

/* 6. Muted helper / "no options" / trading name text */
:deep(.v-select .bs5-muted-text),
:deep(.v-select .vs__no-options),
:deep(.v-select span) {
    color: var(--bs-secondary-color, #6c757d);
}

/* 7. Dropdown arrow & clear button icons */
:deep(.v-select .vs__open-indicator),
:deep(.v-select .vs__clear) {
    fill: var(--bs-secondary-color, #6c757d) !important;
}
</style>
