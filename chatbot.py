import os
import json
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def build_system_prompt(form_fields):
    """Build system prompt dynamically based on form fields."""
    
    # Build field list from form_fields
    fields_list = []
    for i, field in enumerate(form_fields, 1):
        field_name = field.get("field")
        field_type = field.get("type", "text")
        description = get_field_description(field_name)
        fields_list.append(f"{i}. {field_name} ({description})")
    
    fields_str = "\n".join(fields_list)
    
    return f"""You are BankBuddy, a friendly assistant helping users fill a bank form.

IMPORTANT: This is a conversation. You will receive:
- The conversation history (previous messages)
- A [Context] block with each user message showing current form state

Use BOTH the conversation history and context to understand what the user needs.

YOUR JOB:
- Have a natural conversation to collect form field values
- Answer questions about the form or banking terms
- Handle corrections ("no, I meant...", "change amount to...")
- When all fields are filled, show summary and ask for confirmation
- Remember what user said earlier in the conversation
- If one field depends on another use the logic and fill yourself, but confirm with user 

FORM FIELDS NEEDED:
{fields_str}


RESPOND WITH JSON ONLY:
{{
    "message": "Your conversational response",
    "extracted_fields": {{"field_name": "value"}},
    "ready_to_generate": true/false
}}
Once all fields are filled, take a confirmation from the user by showing all collected values. 
Set ready_to_generate=true ONLY after user explicitly confirms the summary. Return the final list of values in a clean JSON format without any extra text at the end. 

Be warm, patient, and helpful. Explain things simply if user is confused."""


def get_field_description(field_name):
    """Get description for each field."""
    descriptions = {
        "Date": "DDMMYYYY format",
        "Account Number": "7-12 digits",
        "Account Type": "SB=Savings, RD, TD, MIS, etc.",
        "Credit To": "account holder name",
        "Amount": "numbers only",
        "Amount in Words": "e.g., Five Thousand Only",
        "Cash/DD/Cheque": "cheque/DD number, optional if cash",
        "Date_2": "date on cheque/DD if applicable",
        "IFSC Code": "e.g., SBIN0001234"
    }
    return descriptions.get(field_name, "form field")


class FormAssistant:
    # Each instance of FormAssistant has its own conversation history and field values
    def __init__(self, form_fields):
        self.form_fields = form_fields
        self.field_values = {}
        self.conversation_history = []
        
        # Build system prompt dynamically from form fields
        self.system_prompt = build_system_prompt(form_fields)
        
        # Pre-fill existing values from form_fields
        for field in form_fields:
            value = field.get("value", "")
            if value:
                self.field_values[field.get("field")] = value
    
    def get_unfilled_fields(self):
        """Get list of fields still needing values."""
        all_fields = [f.get("field") for f in self.form_fields]
        return [f for f in all_fields if not self.field_values.get(f)]
    
    def chat(self, user_input):
        """Send message and get response."""
        
        # Inject current state as context (appended to user message)
        unfilled = self.get_unfilled_fields()
        today = datetime.now().strftime("%d%m%Y")
        
        # Context helps model track state reliably + conversation history provides understanding of user
        context = f"\n\n[Context: Today={today}. Filled={self.field_values}. Still needed={unfilled}]"
        
        self.conversation_history.append({
            "role": "user", 
            "content": user_input + context
        })
        
        # Call OpenAI API with system prompt + full conversation history
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                *self.conversation_history
            ],
            response_format={"type": "json_object"},
            temperature=0.4
        )
        
        assistant_msg = response.choices[0].message.content
        self.conversation_history.append({
            "role": "assistant", 
            "content": assistant_msg
        })
        
        # Parse response and update field values
        try:
            result = json.loads(assistant_msg)
            for field, value in result.get("extracted_fields", {}).items():
                if value:
                    self.field_values[field] = value
            result["missing_fields"] = self.get_unfilled_fields()
            return result
        except json.JSONDecodeError:
            return {
                "message": assistant_msg, 
                "extracted_fields": {}, 
                "missing_fields": self.get_unfilled_fields(),
                "ready_to_generate": False
            }
    
    def get_filled_form(self):
        """Return form fields with filled values for PDF generation."""
        filled = []
        for field in self.form_fields:
            f = field.copy()
            f["value"] = self.field_values.get(field.get("field"), "")
            filled.append(f)
        return filled


# --- Main ---
if __name__ == "__main__":
    # Test fields (some pre-filled, some empty)
    test_fields = [
        {"field": "Date", "value": "", "spacing": 18.5},
        {"field": "Account Type", "value": "X", "type": "checkbox"},
        {"field": "Account Number", "value": "2544631", "spacing": 18.5},
        {"field": "Credit To", "value": ""},
        {"field": "Amount", "value": ""},
        {"field": "Amount in Words", "value": ""},
        {"field": "IFSC Code", "value": ""},
    ]
    
    print("=" * 50)
    print("🏦 BankBuddy - Form Filling Assistant")
    print("=" * 50)
    print("Type 'quit' to exit\n")
    
    assistant = FormAssistant(test_fields)
    
    # Initial greeting
    response = assistant.chat("Hi, I need to fill a deposit form for Post Office. Can you help me?")
    print(f"🤖 BankBuddy: {response['message']}\n")
    
    # Chat loop (Whats this for ?)
    while True:
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        if not user_input:
            continue
        
        response = assistant.chat(user_input)
        print(f"\n🤖 BankBuddy: {response['message']}")
        
        if response.get('extracted_fields'):
            print(f"   ✅ Got: {response['extracted_fields']}")
        if response.get('missing_fields'):
            print(f"   📋 Need: {response['missing_fields']}")
        print()
        
        if response.get('ready_to_generate'):
            print("=" * 50)
            print("✅ Generating PDF with:")
            for k, v in assistant.field_values.items():
                print(f"   • {k}: {v}")
            # Call fill_pdf_form() here
            break
