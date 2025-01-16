from pydantic import BaseModel

class AppointmentReturn(BaseModel):
  id: int
  client_name: str
  appointment_date: str
  appointment_time_start: str
  appointment_time_end: str
  barber_id: int
  barber_name: str
  phone_number: str