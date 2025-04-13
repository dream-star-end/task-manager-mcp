
from google import genai
from pydantic import BaseModel


class Recipe(BaseModel):
  recipe_name: str
  ingredients: list[str]


client = genai.Client(api_key="AIzaSyDlyM0EPRL6-KOkquWYuGHEpUAS6obGmkk")
response = client.models.generate_content(
    model='gemini-2.0-flash',
    contents='List a few popular cookie recipes. Be sure to include the amounts of ingredients.',
    config={
        'response_mime_type': 'application/json',
        'response_schema': list[Recipe],
    },
)
# Use the response as a JSON string.
print(response.text)

# Use instantiated objects.
my_recipes: list[Recipe] = response.parsed