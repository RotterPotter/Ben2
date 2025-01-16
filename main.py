import uvicorn
import fastapi
from fastapi.middleware.cors import CORSMiddleware
from barbers.routes import router as barbers_router
from fastapi import Request, Depends
import database
from sqlalchemy.orm import Session
from service import Service
import prompts
import logging 
import json
import datetime 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = fastapi.FastAPI()
app.include_router(barbers_router)
service = Service()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Dialogflow CX origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)
@app.get("/get_appointments_testing")
async def get_appointments_testing(
    db_session: Session = Depends(database.get_db)
):
    return service.get_appointments_from_database("2022-01-01", "2022-01-31", db_session=db_session)

@app.post("/schedule_appointment")
async def schedule_appointment(
    db_session: Session = Depends(database.get_db),
    date: str = None,
    time: str = None,
    barber_name: str = None,
    client_name: str = None
):
    response = service.schedule_appointment(date=date, time=time, barber_name=barber_name, client_name=client_name, db_session=db_session)
    if response == True:
        return {"message": "Appointment scheduled successfully"}
    else:
       return response 
    
@app.post("/webhook")
async def webhook(
    request: Request,
    db_session: Session = Depends(database.get_db)
):
    try:
        # Convert request to JSON
        request_body = await request.json()
        session_id = await service.get_session_id(request_body)
        
        # Save session ID and update history
        await service.save_session_id(session_id, db_session)
        await service.update_history(session_id, db_session, user_message=request_body.get("text"))
        
        # Fetch conversation history
        conversation_history = await service.take_converation_history_for_session_id(session_id, db_session)
        history_dict_list = [message.to_dict() for message in conversation_history[-10:]]  # Last 10 messages
        history_json = json.dumps(history_dict_list, indent=4)

        # Construct the prompt
        current_datetime = datetime.datetime.now()
        main_prompt = prompts.main_prompt
        prompt = f"{main_prompt}\n\nCURRENT CONVERSATION HISTORY:\n{history_json}\nCURRENT DATE: {current_datetime.date()}\nCURRENT TIME: {current_datetime.time()}"

        # AI model request
        model_response = await service.ai_request(prompt=prompt)
        json_from_model = await service.extract_json_from_text(model_response)
        print(model_response)
        if json_from_model:
            # Validate JSON and execute function
            function_name = json_from_model[0]["function_name"]
            function_params = json_from_model[0]["function_params"]
            
            action_function = service.available_actions.get(function_name)
            if action_function:
                result = await action_function(**function_params, db_session=db_session, session_id=session_id)
                await service.update_history(session_id, db_session, bot_message=result)
                return {"fulfillmentText": result}  # Dialogflow CX response format
            else:
                raise ValueError(f"Unknown function: {function_name}")
        else:
            await service.update_history(session_id, db_session, bot_message=model_response)
            return {"fulfillmentText": model_response}  # Dialogflow CX response format
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"fulfillmentText": "An error occurred. Please try again later."}

    


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)