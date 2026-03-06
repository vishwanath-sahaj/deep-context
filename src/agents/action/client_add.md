### Flow 2: Client Management - Create/Edit Client (CRITICAL)

**Description:** User creates a new client or edits existing client information including name and website

**Prerequisites:**
- User must be authenticated (session required)
- User must have appropriate permissions to manage clients

**Estimated Duration:** 10-15 seconds

#### Step 1: NAVIGATE to client form page
- **URL:** `/clients/add` (for creation) or `/clients/edit/[clientID]` (for editing)
- **Expected Outcome:** Client form displayed with input fields
- **Source:** `__tests__/components/clientForm/__snapshots__/clientForm.snapshot.test.tsx.snap`, `src/app/clients/add/page.tsx`, `src/app/clients/edit/[clientID]/page.tsx`

#### Step 2: FILL client name input field

**Element Metadata:**
- **Role:** `textbox` (HTML: `<input>`)
- **Accessible Name:** `"Client Name"`
- **Type:** `text`
- **Placeholder:** (not present in the snapshot)
- **Label:** `"Client Name"` (marked as required)
- **Name:** (not present in the snapshot)
- **Test ID:** `input-text-box`
- **Context:** Client Form component
- **Page Location:** `/clients/add` or `/clients/edit/[clientID]`
- **Aria Attributes:** `aria-describedby="Client Name"`
- **HTML Attributes:** `id="clientName"`, classes include `p-inputtext`, `p-component`, `inputBox`, `data-pc-name="inputtext"`, `data-pc-section="root"`

**Action:** Enter or modify client name  
**Expected Outcome:** Client name field populated  
**Source:** `__tests__/components/clientForm/__snapshots__/clientForm.snapshot.test.tsx.snap`

#### Step 3: FILL website input field

**Element Metadata:**
- **Role:** `textbox` (HTML: `<input>`)
- **Accessible Name:** `"Website"`
- **Type:** `text`
- **Placeholder:** `[UNKNOWN]`
- **Label:** `"Website"` (marked as required)
- **Name:** `[UNKNOWN]`
- **Test ID:** `input-text-box`
- **Context:** Client Form component
- **Page Location:** `/clients/add` or `/clients/edit/[clientID]`
- **Aria Attributes:** `aria-describedby="Website"`
- **HTML Attributes:** `id="website"`, classes include `p-inputtext`, `p-component`, `inputBox`

**Action:** Enter client website URL  
**Expected Outcome:** Website field populated with valid URL  
**Source:** `__tests__/components/clientForm/__snapshots__/clientForm.snapshot.test.tsx.snap`

#### Step 4: SELECT from dropdown (client selection)

**Element Metadata:**
- **Role:** `[UNKNOWN]` (likely `combobox` or `listbox`)
- **Accessible Name:** `[UNKNOWN]`
- **Type:** N/A (select element)
- **Placeholder:** `[UNKNOWN]`
- **Label:** `[UNKNOWN]`
- **Name:** `[UNKNOWN]`
- **Test ID:** `input-select-box`
- **Context:** Client Form component
- **Page Location:** `/clients/add` or `/clients/edit/[clientID]`
- **Aria Attributes:** `[UNKNOWN]`
- **HTML Attributes:** `[UNKNOWN]`

**Action:** Select option from dropdown  
**Expected Outcome:** Selected value displayed in dropdown  
**Source:** `__tests__/components/clientForm/__snapshots__/clientForm.snapshot.test.tsx.snap`

#### Step 5: CLICK submit button

**Element Metadata:**
- **Role:** `button` (HTML: `<button>`)
- **Accessible Name:** `SAVE CLIENT`
- **Type:** `[UNKNOWN]`
- **Placeholder:** N/A
- **Label:** `SAVE CLIENT`
- **Name:** `[UNKNOWN]`
- **Test ID:** `[UNKNOWN]`
- **Context:** Client Form component
- **Page Location:** `/clients/add` or `/clients/edit/[clientID]`
- **Aria Attributes:** `[UNKNOWN]`
- **HTML Attributes:** `[UNKNOWN]`

**Action:** Submit client form  
**Expected Outcome:** Client created/updated, user redirected to client list or details page  
**Source:** `[UNKNOWN]` (form submission handler not visible in provided context)

---