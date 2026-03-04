import os
import json
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"


def is_field_visible(field, filled_values):
    """Check if a field should be shown based on its show_when condition."""
    show_when = field.get("show_when")
    if not show_when:
        return True  # No condition — always visible
    parent_field = show_when.get("field")
    expected_value = show_when.get("equals")
    actual_value = filled_values.get(parent_field, "")
    return actual_value == expected_value


def build_system_prompt(form_fields, filled_values=None):
    """Build system prompt dynamically based on form fields."""
    filled_values = filled_values or {}
    
    # Build field list (filter by show_when visibility and copy_from)
    fields_list = []
    for field in form_fields:
        field_name = field.get("field")
        if field.get("value") or filled_values.get(field_name):
            continue
        # Skip copy_from fields — they auto-inherit from the source field
        if field.get("copy_from"):
            continue
        # Skip fields whose show_when condition is not met
        if not is_field_visible(field, filled_values):
            continue
        desc = field.get("description", "")
        # For radio fields, list the valid options
        if field.get("type") == "radio":
            options = list(field.get("options", {}).keys())
            desc += f" (Options: {', '.join(options)})"
        fields_list.append(f"- {field_name}: {desc}")
    
    fields_str = "\n".join(fields_list) if fields_list else "All fields are filled!"
    
    return f"""You are Bank Form Assistant, a friendly assistant helping users fill a bank form.

FIELDS STILL NEEDED:
{fields_str}

RULES:

1. EXTRACT AGGRESSIVELY: When the user sends a message, extract EVERY field you can from it. A single message often contains multiple field values — get them all.

2. BE SMART ABOUT RELATED FIELDS: If you can compute or infer a field from information you already have, fill it yourself. Never ask the user for something you can figure out, or for duplicate fields. For ex, if you have amount in number, you can convert it to words. 

3. ASK EFFICIENTLY: Request all remaining unfilled fields together in one question. Don't ask one field at a time. Only if you feel the user has given wrong/conflicting info, ask for clarification on that specific point. 

4. UNDERSTAND INTENT: Map natural language to the right fields. "through cheque" means the payment mode is Cheque. "cash deposit" means Cash. Infer, don't ask.

5. USE CONTEXT: The [Context] block shows what's filled and what's still needed. Never re-ask for filled fields. Check which language is being used in conversation and ensure to continue the conversation in the same language the user is using.

RESPOND WITH JSON ONLY:
{{
    "message": "Your conversational response",
    "extracted_fields": {{"field_name": "value", ...}},
    "ready_to_generate": true/false
}}

When all fields are filled, show a summary and ask user to confirm.
Set ready_to_generate=true ONLY after user explicitly confirms.

Be warm, helpful, and EFFICIENT — minimize the number of questions."""

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
        """Get list of fields still needing values (respects show_when and copy_from)."""
        unfilled = []
        for f in self.form_fields:
            field_name = f.get("field")
            if self.field_values.get(field_name):
                continue
            # copy_from fields auto-inherit — never count as unfilled
            if f.get("copy_from"):
                continue
            if not is_field_visible(f, self.field_values):
                continue
            unfilled.append(field_name)
        return unfilled
    
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
            # Rebuild prompt so show_when conditions are re-evaluated
            self.system_prompt = build_system_prompt(self.form_fields, self.field_values)
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
    
    return f"""You are Bank Form Assistant, a friendly banking assistant helping users find and fill bank forms.

AVAILABLE FORMS:
{json.dumps(form_info, indent=2)}

YOUR JOB:
- Greet the user warmly and ask what they need help with
- Through natural conversation, understand which form they need
- If they mention something that matches a form (or its aliases), identify it
- If unclear, ask clarifying questions
- If they want a form you don't have, politely explain what IS available
- If user wants to end the conversation, say goodbye
- Respond in the same language the user is using

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
            return "Hello! I'm your Bank Form Assistant. How can I help you with your banking forms today?"


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
    print("🏦 Bank Form Assistant")
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
    print(f"🤖 Assistant: {greeting}\n")
    
    # Phase 1: Form Detection Conversation
    form_name = None
    bank_name = None
    
    while True:
        user_input = input("👤 You: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n🤖 Assistant: Goodbye! Have a great day! 👋")
            exit()
        
        response = form_finder.chat(user_input)
        print(f"\n🤖 Assistant: {response.get('message', '')}\n")
        
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
    print(f"🤖 Assistant: {initial_response['message']}\n")
    
    # Phase 3: Form Filling Conversation
    while True:
        user_input = input("👤 You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        if not user_input:
            continue
        
        response = assistant.chat(user_input)
        print(f"\n🤖 Assistant: {response['message']}\n")
        
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
