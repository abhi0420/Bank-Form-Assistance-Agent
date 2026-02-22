"""
Flask backend for BankBuddy Form Assistant
"""
import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

# Import from chatbot.py to avoid duplication
from chatbot import (
    load_available_forms,
    load_form_coordinates,
    get_all_forms_flat,
    get_form_details,
    load_form_fields,
    build_form_finder_prompt,
    build_system_prompt as build_form_filling_prompt
)

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

# Store active sessions (in production, use Redis or database)
sessions = {}


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/forms')
def get_forms():
    """Get all available forms grouped by bank."""
    available_forms = load_available_forms()
    return jsonify(available_forms)


@app.route('/api/session/start', methods=['POST'])
def start_session():
    """Start a new chat session."""
    session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    available_forms = load_available_forms()
    
    sessions[session_id] = {
        "phase": "detection",  # detection or filling
        "conversation_history": [],
        "available_forms": available_forms,
        "form_name": None,
        "bank_name": None,
        "field_values": {},
        "form_fields": []
    }
    
    return jsonify({"session_id": session_id})


@app.route('/api/session/select-form', methods=['POST'])
def select_form():
    """Directly select a form (skip detection phase)."""
    data = request.json
    session_id = data.get("session_id")
    form_name = data.get("form_name")
    bank_name = data.get("bank_name")
    
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    
    session = sessions[session_id]
    available_forms = session["available_forms"]
    
    # Get form details
    form_details = get_form_details(available_forms, form_name, bank_name)
    if not form_details:
        return jsonify({"error": "Form not found"}), 404
    
    # Load form fields
    coordinates_file = form_details.get("coordinates_file", "field_coordinates.json")
    form_fields = load_form_fields(coordinates_file, form_name)
    
    if not form_fields:
        return jsonify({"error": "Could not load form fields"}), 500
    
    # Update session
    session["phase"] = "filling"
    session["form_name"] = form_name
    session["bank_name"] = bank_name
    session["form_fields"] = form_fields
    session["coordinates_file"] = coordinates_file
    session["conversation_history"] = []
    
    # Pre-fill values from form_fields (if any have default values)
    for field in form_fields:
        if field.get("value"):
            session["field_values"][field.get("field")] = field.get("value")
    
    # Generate initial message (skip pre-filled fields)
    system_prompt = build_form_filling_prompt(form_fields, session["field_values"])
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"I want to fill the {form_name} form. What information do you need?"}
        ],
        response_format={"type": "json_object"},
        temperature=0.4
    )
    
    result = json.loads(response.choices[0].message.content)
    
    session["conversation_history"].append({
        "role": "user",
        "content": f"I want to fill the {form_name} form. What information do you need?"
    })
    session["conversation_history"].append({
        "role": "assistant",
        "content": response.choices[0].message.content
    })
    
    return jsonify({
        "message": result.get("message"),
        "form_name": form_name,
        "bank_name": bank_name,
        "phase": "filling"
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat message."""
    data = request.json
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()
    
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    
    session = sessions[session_id]
    
    if session["phase"] == "detection":
        return handle_detection_chat(session, user_message)
    else:
        return handle_filling_chat(session, user_message)


def handle_detection_chat(session, user_message):
    """Handle chat during form detection phase."""
    available_forms = session["available_forms"]
    system_prompt = build_form_finder_prompt(available_forms)
    
    session["conversation_history"].append({
        "role": "user",
        "content": user_message
    })
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            *session["conversation_history"]
        ],
        response_format={"type": "json_object"},
        temperature=0.4
    )
    
    assistant_msg = response.choices[0].message.content
    session["conversation_history"].append({
        "role": "assistant",
        "content": assistant_msg
    })
    
    result = json.loads(assistant_msg)
    
    response_data = {
        "message": result.get("message"),
        "phase": "detection",
        "end_conversation": result.get("end_conversation", False)
    }
    
    # Check if form was identified
    if result.get("form_name") and result.get("confidence") in ["high", "medium"]:
        form_name = result.get("form_name")
        bank_name = result.get("bank")
        
        # Load form details and transition to filling phase
        form_details = get_form_details(available_forms, form_name, bank_name)
        if form_details:
            coordinates_file = form_details.get("coordinates_file", "field_coordinates.json")
            form_fields = load_form_fields(coordinates_file, form_name)
            
            if form_fields:
                session["phase"] = "filling"
                session["form_name"] = form_name
                session["bank_name"] = bank_name
                session["form_fields"] = form_fields
                session["coordinates_file"] = coordinates_file
                session["conversation_history"] = []  # Reset for filling phase
                
                response_data["phase"] = "filling"
                response_data["form_name"] = form_name
                response_data["bank_name"] = bank_name
    
    return jsonify(response_data)


def handle_filling_chat(session, user_message):
    """Handle chat during form filling phase."""
    form_fields = session["form_fields"]
    field_values = session["field_values"]
    
    # Get unfilled fields
    all_fields = [f.get("field") for f in form_fields]
    unfilled = [f for f in all_fields if not field_values.get(f)]
    
    today = datetime.now().strftime("%d%m%Y")
    context = f"\n\n[Context: Today={today}. Filled={field_values}. Still needed={unfilled}]"
    
    session["conversation_history"].append({
        "role": "user",
        "content": user_message + context
    })
    
    # Rebuild prompt with current filled values so it only shows unfilled fields
    system_prompt = build_form_filling_prompt(form_fields, field_values)
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            *session["conversation_history"]
        ],
        response_format={"type": "json_object"},
        temperature=0.4
    )
    
    assistant_msg = response.choices[0].message.content
    session["conversation_history"].append({
        "role": "assistant",
        "content": assistant_msg
    })
    
    result = json.loads(assistant_msg)
    
    # Update field values
    for field, value in result.get("extracted_fields", {}).items():
        if value:
            session["field_values"][field] = value
    
    response_data = {
        "message": result.get("message"),
        "phase": "filling",
        "form_name": session["form_name"],
        "field_values": session["field_values"],
        "ready_to_generate": result.get("ready_to_generate", False)
    }
    
    return jsonify(response_data)


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """Generate the filled PDF."""
    data = request.json
    session_id = data.get("session_id")
    
    if session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 400
    
    session = sessions[session_id]
    
    if session["phase"] != "filling":
        return jsonify({"error": "Form not selected yet"}), 400
    
    from fill_form import fill_pdf_from_chatbot
    
    output_path = fill_pdf_from_chatbot(
        chatbot_values=session["field_values"],
        json_path=session.get("coordinates_file", "field_coordinates.json"),
        form_name=session["form_name"]
    )
    
    if output_path:
        return jsonify({
            "success": True,
            "output_path": output_path,
            "field_values": session["field_values"]
        })
    else:
        return jsonify({"error": "Failed to generate PDF"}), 500


@app.route('/api/download/<path:filename>')
def download_file(filename):
    """Download generated PDF."""
    return send_file(filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
