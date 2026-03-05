"""Test script for Flow Identifier agent."""

import sys
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.flow_identifier import FlowIdentifierAgent


def test_flow_identifier():
    """Test the flow identifier with a sample codebase summary."""
    
    # Sample codebase summary (similar to what the codebase tool would return)
    codebase_summary = """
    # Frontend Codebase Summary

    ## Authentication Flow
    The application has a login page located at `/login` route in `src/routes/auth.tsx`.
    
    ### Login Form Component (src/components/LoginForm.tsx)
    - Email input field:
      * HTML: `<input type="email" placeholder="Enter your email" />`
      * Has label: "Email Address"
      * Located at line 67
      * Required field
    
    - Password input field:
      * HTML: `<input type="password" />`
      * Has label: "Password"
      * Located at line 78
      * Required field
    
    - Submit button:
      * HTML: `<button type="submit">Sign In</button>`
      * Located at line 89
      * On submit, calls `handleLogin` from `src/hooks/useAuth.ts:120`
      * Success: redirects to `/dashboard`
      * Shows welcome message on successful login
    
    ## Dashboard
    After successful login, user is redirected to `/dashboard` route (src/routes/dashboard.tsx).
    Shows personalized welcome message with user's name.
    """
    
    print("=" * 80)
    print("FLOW IDENTIFIER TEST")
    print("=" * 80)
    print("\n📝 Input Codebase Summary:")
    print("-" * 80)
    print(codebase_summary)
    print("-" * 80)
    
    # Initialize agent
    print("\n🤖 Initializing Flow Identifier Agent...")
    agent = FlowIdentifierAgent()
    
    # Test flow identification
    print("\n🔍 Extracting flows from codebase summary...")
    print("(This will call Claude API - may take a few seconds)")
    
    try:
        result = agent.identify_flows(
            codebase_summary=codebase_summary,
            request_missing_metadata=True
        )
        
        print("\n✅ Flow extraction complete!")
        print("=" * 80)
        print("\n📋 EXTRACTED FLOWS:")
        print("=" * 80)
        print(result.flows_markdown)
        print("=" * 80)
        
        if result.followup_queries:
            print("\n⚠️  Missing Metadata Detected!")
            print("=" * 80)
            print(f"\n🔍 Found {len(result.metadata_gaps)} metadata gaps")
            print(f"📝 Generated {len(result.followup_queries)} followup queries:\n")
            
            for i, query in enumerate(result.followup_queries, 1):
                print(f"{i}. {query}")
            
            print("\n" + "=" * 80)
            print("💡 Next Steps:")
            print("   1. Use these queries with the codebase tool")
            print("   2. Pass the results to agent.refine_with_additional_context()")
            print("   3. Get updated flows with complete metadata")
            print("=" * 80)
        else:
            print("\n✅ All metadata is complete!")
            print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during flow identification: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_metadata_refinement():
    """Test the metadata refinement with additional context."""
    
    # Incomplete flows (with [UNKNOWN] markers)
    incomplete_flows = """
# Critical User Flows Analysis

## Flow 1: User Login (CRITICAL)
**Description:** User authenticates with email and password

### Step 1: NAVIGATE to login page
- **URL**: `/login`
- **Expected Outcome**: Login form displayed
- **Source**: `src/routes/auth.tsx:45`

### Step 2: FILL email input field
**Element Metadata:**
- **Role**: `textbox`
- **Accessible Name**: "Email Address"
- **Type**: `email`
- **Placeholder**: "Enter your email"
- **Label**: "Email Address"
- **Test ID**: [UNKNOWN]
- **Context**: LoginForm component

**Expected Outcome**: Email field populated
**Source**: `src/components/LoginForm.tsx:67`
"""
    
    # Additional context from followup query
    additional_context = """
    The email input field in LoginForm.tsx has the following attributes:
    - data-testid="email-input"
    - name="email"
    """
    
    print("\n" + "=" * 80)
    print("METADATA REFINEMENT TEST")
    print("=" * 80)
    
    print("\n📝 Original Flows (with [UNKNOWN]):")
    print("-" * 80)
    print(incomplete_flows)
    print("-" * 80)
    
    print("\n📝 Additional Context:")
    print("-" * 80)
    print(additional_context)
    print("-" * 80)
    
    print("\n🤖 Initializing Flow Identifier Agent...")
    agent = FlowIdentifierAgent()
    
    print("\n🔄 Refining flows with additional context...")
    
    try:
        refined_flows = agent.refine_with_additional_context(
            initial_flows=incomplete_flows,
            additional_context=additional_context
        )
        
        print("\n✅ Refinement complete!")
        print("=" * 80)
        print("\n📋 REFINED FLOWS:")
        print("=" * 80)
        print(refined_flows)
        print("=" * 80)
        
        return refined_flows
        
    except Exception as e:
        print(f"\n❌ Error during refinement: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("FLOW IDENTIFIER AGENT - TEST SUITE")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Extract flows from a sample codebase summary")
    print("2. Validate metadata completeness")
    print("3. Generate followup queries if needed")
    print("4. Test metadata refinement")
    print("\n⚠️  NOTE: This requires a valid CLAUDE_API_KEY in your .env file")
    print("=" * 80)
    
    input("\nPress Enter to start the test...")
    
    # Test 1: Flow Identification
    result = test_flow_identifier()
    
    # Test 2: Metadata Refinement (if user wants)
    if result:
        print("\n" + "=" * 80)
        response = input("\n🤔 Would you like to test metadata refinement? (y/n): ")
        if response.lower() == 'y':
            test_metadata_refinement()
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE!")
    print("=" * 80)
