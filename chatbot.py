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
        fields_list.append(f"{i}. {field_name} ({field_type})")
    
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
- If one field can be used to fill another, do so automatically without asking explicitly, but inform the user about it

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
        
        print()
        
        if response.get('ready_to_generate'):
            print("=" * 50)
            print("✅ Generating PDF with:")
            for k, v in assistant.field_values.items():
                print(f"   • {k}: {v}")
            
            # Generate the PDF
            from fill_form import fill_pdf_from_chatbot
            output_path = fill_pdf_from_chatbot(
                chatbot_values=assistant.field_values,
                json_path="field_coordinates.json",
                form_name="Pay-in-Slip",
                input_pdf="forms/Pay-in-Slip.pdf",
                output_pdf="forms/Pay-in-Slip_filled.pdf"
            )
            
            if output_path:
                print(f"\n🎉 Form filled successfully! Check: {output_path}")
            break
