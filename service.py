from sqlalchemy.orm import Session
from models import DialogSession, DialogMessages, PhoneNumber, Appointment, Barber
from config import settings
from SimplerLLM.language.llm import LLM, LLMProvider
import json 
import re
import datetime 
import prompts
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, Time
from schemas import AppointmentReturn


class Service:
  def __init__(self):
    self.MODEL_API_KEY = settings.GEMINI_API_KEY
    self.MODEL_NAME = "gemini-1.5-pro"
    self.TEMPERATURE = 0.1
    self.llm_instance = LLM.create(LLMProvider.GEMINI,api_key=self.MODEL_API_KEY, model_name=self.MODEL_NAME, temperature=self.TEMPERATURE)
    self.available_actions = {
      "schedule_appointment": self.schedule_appointment,
      "cancel_appointment": self.cancel_appointment,
      "end_conversation": self.end_conversation,
      "get_appointments_from_database": self.get_appointments_from_database,
      "continue_conversation": self.continue_conversation,
      "check_for_availability": self.check_for_availability
    }

  async def check_for_availability(
    self,
    db_session: Session,
    session_id: str,
    date: str = None,
    time: str = None,
    barber_name: str = None,
    date_range: str = None,
    time_range: str = None,
    model_language: str = "English"
):
    # If neither 'date' nor 'date_range' is provided, default to today through two weeks from today
    if not date and not date_range:
        today = datetime.datetime.now().date()
        two_weeks_from_today = today + datetime.timedelta(weeks=2)
        date_range = f"{today}:{two_weeks_from_today}"

    query = db_session.query(Appointment)

    # Filter by exact date if provided
    if date:
        # This works fine in PostgreSQL
        query = query.filter(func.date(Appointment.datetime) == date)

    # Filter by exact time if provided
    if time:
        # Cast datetime to time, then compare
        query = query.filter(cast(Appointment.datetime, Time) == time)

    # Filter by barber name if provided
    if barber_name:
        barber = db_session.query(Barber).filter_by(name=barber_name).first()
        if barber:
            query = query.filter(Appointment.barber == barber)
        else:
            # If the barber doesn't exist, return an empty list
            conversation_history = await self.take_converation_history_for_session_id(session_id, db_session)
            history_dict_list = [message.to_dict() for message in conversation_history[-5:]]  # Last 5 messages
            history_json = json.dumps(history_dict_list, indent=4)
            return await self.ai_helper_request("check_for_availability", "False, Barber does not exist", db_session=db_session, history_json=history_json)

    # Filter by date range if provided
    if date_range:
        try:
            start_date_str, end_date_str = date_range.split(":")
            query = query.filter(
                func.date(Appointment.datetime).between(start_date_str, end_date_str)
            )
        except ValueError:
            raise ValueError("Invalid date_range format. Use 'YYYY-MM-DD:YYYY-MM-DD'.")

    # Filter by time range if provided
    if time_range:
        try:
            start_time_str, end_time_str = time_range.split("-")
            # Use casting for the time portion
            query = query.filter(
                cast(Appointment.datetime, Time).between(start_time_str, end_time_str)
            )
        except ValueError:
            raise ValueError("Invalid time_range format. Use 'HH:MM-HH:MM'.")

    # Retrieve, convert to dict, etc.
    appointments = query.all()
    appointments = [appointment.to_dict() for appointment in appointments]
    appointments_json = json.dumps(appointments, indent=4)

    provided_data = {
        "date": date,
        "time": time,
        "barber_name": barber_name,
        "date_range": date_range,
        "time_range": time_range
    }
    
    prompt = prompts.check_availability_prompt
    current_datetime = datetime.datetime.now()
    input_data = f"""
      Input Data:
      - **APPOINTMENTS FROM DATABASE**: {appointments_json}
      - **CURRENT DATE**: {current_datetime.date()}
      - **CURRENT TIME**: {current_datetime.time()}
      - **RESPONSE LANGUAGE**: {model_language}
      - **PROVIDED DATA**: {provided_data}
      Output:
      - A textual response in the format described above, in the specified **RESPONSE LANGUAGE**.
    """
    prompt += input_data
    result = await self.ai_request(prompt=prompt)
    return result 
         
  async def continue_conversation(self, db_session: Session, session_id: str):
      return True
  
  async def get_appointments_from_database(self, date_start: str, date_end: str, db_session: Session, session_id: str = None):
      date_start = datetime.datetime.strptime(date_start, "%Y-%m-%d")
      date_end = datetime.datetime.strptime(date_end, "%Y-%m-%d")
      appointments = db_session.query(Appointment).filter(Appointment.datetime >= date_start, Appointment.datetime <= date_end).all()
      return appointments
  
  async def format_phone_number(self, phone_number: str) -> str:
    # Remove any non-numeric characters (spaces, parentheses, etc.)
    formatted_number = re.sub(r'\D', '', phone_number)
    # If the number starts with +39, keep the plus sign and country code
    if formatted_number.startswith('39'):
        formatted_number = '+' + formatted_number
    return formatted_number
  
  async def schedule_appointment(self, date: str, time: str, barber_name: str, client_name: str, phone_number: str, db_session: Session, session_id: str):
      # Fetch conversation history
      conversation_history = await self.take_converation_history_for_session_id(session_id, db_session)
      history_dict_list = [message.to_dict() for message in conversation_history[-5:]]  # Last 5 messages
      history_json = json.dumps(history_dict_list, indent=4)
      if not client_name or not phone_number:
        
        input_data = f"""
        Input Data:
        - **CONVERSATION HISTORY**: {history_json}
        - **PHONE NUMBER**: {phone_number}
        - **CLIENT NAME**: {client_name}
        """
        prompt = prompts.ask_additional_client_info_prompt + "\n" + input_data
        response = await self.ai_request(prompt=prompt)
        return response
      
      try:
        phone_number = await self.format_phone_number(phone_number)
        appointment_datetime = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")                
        barber = db_session.query(Barber).filter(Barber.name == barber_name).first()
        phone_number_model = PhoneNumber(number=phone_number, client_name=client_name)
        db_session.add(phone_number_model)
        db_session.commit()

        if not barber:
            function_output = "False, Barber not found"
            return await self.ai_helper_request(function_name="schedule_appointment", function_output=function_output, db_session=db_session, history_json=history_json)
        
        if db_session.query(Appointment).filter(Appointment.datetime == appointment_datetime, Appointment.barber_id == barber.id).first():
            function_output = "False, Slot Already Booked"
            return await self.ai_helper_request(function_name="schedule_appointment", function_output=function_output, db_session=db_session, history_json=history_json)
        
        appointment = Appointment(datetime=appointment_datetime, client_name=client_name, barber=barber, phone_number=phone_number)
        db_session.add(appointment)
        db_session.commit()
      except Exception as e:
        return False, f"Error scheduling appointment\n {e}"
      function_output = "True"
      return await self.ai_helper_request(function_name="schedule_appointment", function_output=function_output, db_session=db_session, history_json=history_json)
      
  
  async def cancel_appointment(self, phone_number: str, db_session: Session, session_id: str):
      try:
        phone_number = await self.format_phone_number(phone_number)
        appointment = db_session.query(Appointment).filter_by(phone_number=phone_number).first()
        if not appointment:
          function_output = f"False, Appointment with this number - {phone_number} not found"
          return await self.ai_helper_request(function_name="cancel_appointment", function_output=function_output, db_session=db_session, history_json=history_json)
        db_session.delete(appointment)
        db_session.commit()
      except:
        return False, "Error cancelling appointment"
      
      conversation_history = await self.take_converation_history_for_session_id(session_id, db_session)
      history_dict_list = [message.to_dict() for message in conversation_history[-5:]]  # Last 5 messages
      history_json = json.dumps(history_dict_list, indent=4)

      function_output = "True"
      return await self.ai_helper_request(function_name="cancel_appointment", function_output=function_output, db_session=db_session, history_json=history_json)
  
  async def end_conversation(self, db_session: Session, session_id: str):
      pass
  
  
  async def get_session_id(self, request: dict):
      return request.get("sessionInfo").get("session").split("/")[-1]
    
  async def save_session_id(self, session_id: str, db_session: Session):
      # Save session ID to database
      if not db_session.query(DialogSession).filter(DialogSession.id == session_id).first():
          db_session.add(DialogSession(id=session_id))
          db_session.commit()

  async def update_history(self, session_id: str, db_session: Session, user_message: str = None, bot_message: str = None):
      # Fetch the dialog session
      dialog_session = db_session.query(DialogSession).filter(DialogSession.id == session_id).first()

      # Add user message to conversation history
      if user_message:
          user_dialog_message = DialogMessages(session_id=session_id, user_message=user_message)
          dialog_session.conversation_history.append(user_dialog_message)
          db_session.commit()
      if bot_message:
          conversation_history = dialog_session.conversation_history
          conversation_history[-1].bot_message = bot_message
          db_session.commit()
  
  async def take_converation_history_for_session_id(self, session_id:str, db_session: Session):
    dialog_session = db_session.query(DialogSession).filter(DialogSession.id == session_id).first()
    return dialog_session.conversation_history
  
  async def ai_request(self, prompt: str) -> str:
      return self.llm_instance.generate_response(messages=[{"role": "user", "content": prompt}])
    
  async def extract_json_from_text(self, text):
    """
    Extracts JSON objects from a given string.

    Args:
        text (str): The input string containing potential JSON objects.

    Returns:
        list: A list of parsed JSON objects extracted from the text.
    """
    # Use regex to find JSON-like blocks
    json_matches = re.findall(r'\{.*?\}', text, re.DOTALL)

    extracted_json_objects = []

    for match in json_matches:
        try:
            # Remove comments (//) from JSON
            cleaned_match = re.sub(r'//.*$', '', match, flags=re.MULTILINE)
            # Remove trailing commas before closing braces or brackets
            cleaned_match = re.sub(r',\s*([}\]])', r'\1', cleaned_match)
            # Fix missing closing braces by appending '}' if necessary
            open_braces = cleaned_match.count('{')
            close_braces = cleaned_match.count('}')
            if open_braces > close_braces:
                cleaned_match += '}' * (open_braces - close_braces)
            # Debug: Print the cleaned JSON block before parsing
            print(f"Attempting to parse cleaned JSON block:\n{cleaned_match}\n")
            # Parse the cleaned JSON string
            json_obj = json.loads(cleaned_match)            
            extracted_json_objects.append(json_obj)
        except json.JSONDecodeError as e:
            # Debug: Print error and the failing block
            print(f"Failed to parse JSON: {e} | Block: {cleaned_match}\n")
            continue

    return extracted_json_objects
  
  async def ai_helper_request(self, function_name: str, function_output: str, db_session: Session, history_json: json):
     input_data = f"""
        Input Data:
        - **CONVERSATION HISTORY**: {history_json}
        - **FUNCTION NAME**: {function_name}
        - **FUNCTION OUTPUT**: {function_output}
        """
     prompt = prompts.ai_helper_prompt + "\n" + input_data
     return await self.ai_request(prompt=prompt)

  async def get_appointments_for_front(self, db_session: Session, date:datetime.datetime=None,):
    # Initialize the query
    query = db_session.query(Appointment)

    # Apply date filter if provided
    if date:
        query = query.filter(cast(Appointment.datetime, Date) == date.date())

    # Sort appointments by datetime
    appointments = query.order_by(Appointment.datetime).all()

    # Transform appointments into the desired format
    appointments_to_return = []
    for appointment in appointments:
        appointment_data = AppointmentReturn(
            id=appointment.id,
            client_name=appointment.client_name,
            appointment_date=appointment.datetime.strftime("%Y-%m-%d"),
            appointment_time_start=appointment.datetime.strftime("%H:%M"),
            appointment_time_end=(appointment.datetime + datetime.timedelta(minutes=30)).strftime("%H:%M"),
            barber_id=appointment.barber_id,
            barber_name=appointment.barber.name,
            phone_number=appointment.phone_number
        )
        appointments_to_return.append(appointment_data)

    return appointments_to_return

  async def generate_dialogflow_response(self, parameters: dict, fullfilment_message: str) -> dict:
        response = {
            "sessionInfo": {
                "parameters": parameters
            },
            "fulfillmentResponse": {
                "messages": [
                    {
                        "text": {
                            "text": [fullfilment_message]
                        }
                    }
                ]
            }
        }
        return response
      