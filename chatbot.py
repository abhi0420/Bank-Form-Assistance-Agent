import os
import json
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def build_system_prompt(form_fields, filled_values=None):
    """Build system prompt dynamically based on form fields."""
    filled_values = filled_values or {}
    
    # Build field list from form_fields
    fields_list = []
    for i, field in enumerate(form_fields, 1):
        field_name = field.get("field")
        # Skip fields that already have values (pre-filled or collected)
        if field.get("value") or filled_values.get(field_name):
            continue
        field_type = field.get("type", "text")
        field_desc = field.get("description", "")
        fields_list.append(f"{i}. {field_name} ({field_type}) - {field_desc}")
    
    fields_str = "\n".join(fields_list) if fields_list else "All fields are filled!"
    
    return f"""You are BankBuddy, a friendly assistant helping users fill a bank form.

IMPORTANT: This is a conversation. You will receive:
- The conversation history 
- A [Context] block with each user message showing current form state

Use BOTH the conversation history and context to understand what the user needs.

YOUR JOB:
- Have a natural conversation to collect form field values
- Answer questions about the form or banking terms
- Handle corrections ("no, I meant...", "change amount to...")
- When all fields are filled, show summary and ask for confirmation
- Remember what user said earlier in the conversation
- If user provides all needed info in one go, that's great! Just confirm at once and summarize back to them. 
- Don't ask for fields you can infer from the info you have. 
For ex Amount in words can be inferred from amount in numbers. 

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


def load_available_forms(json_path="available_forms.json"):
    """Load catalog of available forms."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_form_coordinates(json_path):
    """Load detailed form coordinates from JSON."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_all_forms_flat(available_forms):
    """Flatten the bank->forms structure for LLM detection."""
    all_forms = []
    for bank_entry in available_forms:
        bank_name = bank_entry.get("bank")
        for form in bank_entry.get("forms", []):
            all_forms.append({
                "bank": bank_name,
                "form_name": form.get("form_name"),
                "description": form.get("description", ""),
                "aliases": form.get("aliases", []),
                "pdf_path": form.get("pdf_path"),
                "coordinates_file": form.get("coordinates_file")
            })
    return all_forms


def build_form_finder_prompt(available_forms):
    """Build system prompt for form detection conversation."""
    all_forms = get_all_forms_flat(available_forms)
    
    form_info = []
    for f in all_forms:
        form_info.append({
            "bank": f["bank"],
            "form_name": f["form_name"],
            "description": f["description"],
            "aliases": f["aliases"]
        })
    
    return f"""You are BankBuddy, a friendly banking assistant helping users find and fill bank forms.

AVAILABLE FORMS:
{json.dumps(form_info, indent=2)}

YOUR JOB:
- Greet the user warmly and ask what they need help with
- Through natural conversation, understand which form they need
- If they mention something that matches a form (or its aliases), identify it
- If unclear, ask clarifying questions
- If they want a form you don't have, politely explain what IS available
- If user wants to end the conversation, say goodbye

RESPOND WITH JSON ONLY:
{{
    "message": "Your conversational response to the user",
    "form_name": "exact form_name from list if identified, otherwise null",
    "bank": "bank name if form identified, otherwise null",
    "confidence": "high/medium/low",
    "end_conversation": true/false
}}

Set end_conversation=true ONLY if user explicitly wants to quit/exit/end.
Set form_name only when you're confident about which form they need.

Be warm, helpful, and conversational. Don't be robotic."""


class FormFinder:
    """Conversational assistant to help user find the right form."""
    
    def __init__(self, available_forms):
        self.available_forms = available_forms
        self.system_prompt = build_form_finder_prompt(available_forms)
        self.conversation_history = []
    
    def chat(self, user_input):
        """Send message and get response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
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
        
        try:
            return json.loads(assistant_msg)
        except json.JSONDecodeError:
            return {
                "message": assistant_msg,
                "form_name": None,
                "bank": None,
                "confidence": "low",
                "end_conversation": False
            }
    
    def get_greeting(self):
        """Get initial greeting from assistant."""
        # Prime the conversation with a greeting request
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": "[System: Generate your opening greeting to the user]"}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            return result.get("message", "Hello! How can I help you today?")
        except:
            return "Hello! I'm BankBuddy. How can I help you with your banking forms today?"


def get_form_details(available_forms, form_name, bank_name=None):
    """Get form details including coordinates file path."""
    for bank_entry in available_forms:
        if bank_name and bank_entry.get("bank") != bank_name:
            continue
        for form in bank_entry.get("forms", []):
            if form.get("form_name") == form_name:
                return {
                    "bank": bank_entry.get("bank"),
                    **form
                }
    return None


def load_form_fields(coordinates_file, form_name):
    """Load form fields from coordinates file."""
    forms = load_form_coordinates(coordinates_file)
    for form in forms:
        if form.get("form_name") == form_name:
            return form.get("form_fields", [])
    return []


# --- Main ---
if __name__ == "__main__":
    print("=" * 50)
    print("🏦 BankBuddy - Form Filling Assistant")
    print("=" * 50)
    
    # Load catalog of available forms
    available_forms = load_available_forms("available_forms.json")
    all_forms = get_all_forms_flat(available_forms)
    
    print(f"\n📋 Available forms:")
    for f in all_forms:
        print(f"   • {f['form_name']} ({f['bank']})")
    print()
    
    # Initialize form finder assistant
    form_finder = FormFinder(available_forms)
    
    # Get and show greeting
    greeting = form_finder.get_greeting()
    print(f"🤖 BankBuddy: {greeting}\n")
    
    # Phase 1: Form Detection Conversation
    form_name = None
    bank_name = None
    
    while True:
        user_input = input("👤 You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n🤖 BankBuddy: Goodbye! Have a great day! 👋")
            exit()
        
        response = form_finder.chat(user_input)
        print(f"\n🤖 BankBuddy: {response.get('message', '')}\n")
        
        # Check if user wants to end
        if response.get("end_conversation"):
            print("👋 Goodbye!")
            exit()
        
        # Check if form was identified
        if response.get("form_name") and response.get("confidence") in ["high", "medium"]:
            form_name = response.get("form_name")
            bank_name = response.get("bank")
            break
    
    # Phase 2: Load form and start filling
    print(f"🔍 Great! Let's fill the {form_name} form.\n")
    
    # Get form details from catalog
    form_details = get_form_details(available_forms, form_name, bank_name)
    
    if not form_details:
        print(f"❌ Could not find form details for: {form_name}")
        exit()
    
    # Load form fields from coordinates file
    coordinates_file = form_details.get("coordinates_file", "field_coordinates.json")
    form_fields = load_form_fields(coordinates_file, form_name)
    
    if not form_fields:
        print(f"❌ Could not load form fields from: {coordinates_file}")
        exit()
    
    pdf_path = form_details.get("pdf_path", f"forms/{form_name}.pdf")
    
    print(f"📄 Form: {form_name} ({bank_name})")
    print(f"📁 PDF: {pdf_path}")
    print("-" * 50)
    print("Type 'quit' to exit anytime\n")
    
    # Initialize form filling assistant
    assistant = FormAssistant(form_fields)
    
    # Get initial prompt from form assistant
    initial_response = assistant.chat(f"I want to fill the {form_name} form. What information do you need?")
    print(f"🤖 BankBuddy: {initial_response['message']}\n")
    
    # Phase 3: Form Filling Conversation
    while True:
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        if not user_input:
            continue
        
        response = assistant.chat(user_input)
        print(f"\n🤖 BankBuddy: {response['message']}\n")
        
        if response.get('ready_to_generate'):
            print("=" * 50)
            print("✅ Generating PDF with:")
            for k, v in assistant.field_values.items():
                print(f"   • {k}: {v}")
            
            # Generate the PDF
            from fill_form import fill_pdf_from_chatbot
            output_path = fill_pdf_from_chatbot(
                chatbot_values=assistant.field_values,
                json_path=coordinates_file,
                form_name=form_name
            )
            
            if output_path:
                print(f"\n🎉 Form filled successfully! Check: {output_path}")
            break
