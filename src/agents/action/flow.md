
### Flow 3: Contact Management - Add/Edit Contact (CRITICAL)

**Description:** User creates a new contact or edits existing contact information including name and role

**Prerequisites:**
- User must be authenticated (session required)
- User must have appropriate permissions to manage contacts

**Estimated Duration:** 10-15 seconds

#### Step 1: NAVIGATE to contact form page
- **URL:** `/contacts/add` or `/contacts/edit/[contactID]`
- **Expected Outcome:** Contact form displayed with input fields
- **Source:** `__tests__/contacts/add/__snapshots__/page.snapshot.test.tsx.snap`, `__tests__/contacts/edit/[contactID]/__snapshots__/page.snapshot.test.tsx.snap`

#### Step 2: FILL last name input field

**Element Metadata:**
- **Role:** `textbox` (HTML: `<input>`)
- **Accessible Name:** `"Last Name"`
- **Type:** `text`
- **Placeholder:** `[UNKNOWN]`
- **Label:** `"Last Name"`
- **Name:** `[UNKNOWN]`
- **Test ID:** `input-text-box`
- **Context:** Contact Form component (Add or Edit)
- **Page Location:** `/contacts/add` or `/contacts/edit/[contactID]`
- **Aria Attributes:** `aria-describedby="Last Name"`
- **HTML Attributes:** `id="lastName"`, classes include `p-inputtext`, `p-component`, `inputBox`, `data-pc-name="inputtext"`, `data-pc-section="root"`

**Action:** Enter contact's last name  
**Expected Outcome:** Last name field populated  
**Source:** `__tests__/contacts/add/__snapshots__/page.snapshot.test.tsx.snap`, `__tests__/contacts/edit/[contactID]/__snapshots__/page.snapshot.test.tsx.snap`

#### Step 3: FILL middle name input field (Add flow only)

**Element Metadata:**
- **Role:** `textbox` (HTML: `<input>`)
- **Accessible Name:** `"Middle Name"`
- **Type:** `text`
- **Placeholder:** (empty/not specified)
- **Label:** `"Middle Name"`
- **Name:** `[UNKNOWN]`
- **Test ID:** `input-text-box`
- **Context:** Contact Form component (Add)
- **Page Location:** `/contacts/add`
- **Aria Attributes:** `aria-describedby="Middle Name"`
- **HTML Attributes:** `id="middleName"`, classes include `p-inputtext`, `p-component`, `inputBox`

**Action:** Enter contact's middle name (optional)  
**Expected Outcome:** Middle name field populated  
**Source:** `__tests__/contacts/add/__snapshots__/page.snapshot.test.tsx.snap`

#### Step 4: FILL role input field (Edit flow)

**Element Metadata:**
- **Role:** `textbox` (HTML: `<input>`)
- **Accessible Name:** `"Role"`
- **Type:** `text`
- **Placeholder:** `[UNKNOWN]`
- **Label:** `"Role"` (marked as required)
- **Name:** `[UNKNOWN]`
- **Test ID:** `input-text-box`
- **Context:** Contact Form component (Edit)
- **Page Location:** `/contacts/edit/[contactID]`
- **Aria Attributes:** `aria-describedby="Role"`
- **HTML Attributes:** `id="role"`, classes include `p-inputtext`, `p-component`, `inputBox`, `p-filled`

**Action:** Enter or modify contact's role  
**Expected Outcome:** Role field populated with job title/role  
**Source:** `__tests__/contacts/edit/[contactID]/__snapshots__/page.snapshot.test.tsx.snap`

#### Step 5: CLICK submit button

**Element Metadata:**
- **Role:** `button` (HTML: `<button>`)
- **Accessible Name:** `[UNKNOWN]`
- **Type:** `[UNKNOWN]`
- **Placeholder:** N/A
- **Label:** `[UNKNOWN]`
- **Name:** `[UNKNOWN]`
- **Test ID:** `[UNKNOWN]`
- **Context:** Contact Form component
- **Page Location:** `/contacts/add` or `/contacts/edit/[contactID]`
- **Aria Attributes:** `[UNKNOWN]`
- **HTML Attributes:** `[UNKNOWN]`

**Action:** Submit contact form  
**Expected Outcome:** Contact created/updated, user redirected to contact list or details page  
**Source:** `[UNKNOWN]` (form submission handler not visible in provided context)

---

## �� Additional Notes

### Authentication Context

All flows require authentication via `NextAuth.js`:
- **Session Management:** `getServerSession(authOptions)` (server-side) or `useSession()` (client-side)
- **Auth Configuration:** `src/app/api/auth/lib/auth.ts`
- **Auth Route:** `/api/auth/[...nextauth]`
- **Source:** `src/app/components/navbar/index.tsx`, `src/app/(vipanan)/devdays/create/page.tsx`

### Common UI Patterns

- **PrimeNG Components:** All form inputs use PrimeNG library with classes `p-inputtext`, `p-component`
- **Test ID Convention:** Text inputs use `data-testid="input-text-box"`, select boxes use `data-testid="input-select-box"`
- **Styling:** Custom class `inputBox` applied to all form inputs
- **Data Attributes:** `data-pc-name="inputtext"`, `data-pc-section="root"` for PrimeNG components

### Missing Critical Information

- **Login/Signup Flow:** Form fields, buttons, and navigation not visible in provided context
- **Submit Button Details:** No metadata available for form submission buttons
- **Validation Messages:** Error handling and validation feedback not documented
- **Success/Redirect Behavior:** Post-submission navigation not specified in snapshots
- **Placeholder and Name Attributes:** Not visible in rendered HTML snapshots for most input fields