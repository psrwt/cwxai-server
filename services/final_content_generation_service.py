import openai
from dotenv import load_dotenv
import os
import time  # Added for timing measurements


# Load environment variables
load_dotenv()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")

# Configure Azure OpenAI
openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_API_KEY
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_version = "2024-08-01-preview"



SYSTEM_ROLE = "You are a highly skilled business analyst.  You are excellent at extracting key insights from data and presenting them clearly."

def _generate_content(prompt, max_tokens=500, temperature=0.7):
    """Helper function to call OpenAI and handle errors."""
    start_time = time.time()
    try:
        response = openai.ChatCompletion.create(
            engine=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_ROLE},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        result = {
            "content": response['choices'][0]['message']['content'],
            "time_taken": time.time() - start_time,
            "input_tokens": response['usage']['prompt_tokens'],
            "output_tokens": response['usage']['completion_tokens']
        }
        return result
    except Exception as e:
        result = {
            "content": f"Error generating content: {str(e)}",
            "time_taken": time.time() - start_time,
            "input_tokens": 0,
            "output_tokens": 0
        }
        return result
        
# ==================== Section-Specific Functions ====================

def get_overview(industry: str, target_market: str, problem_description: str) -> dict:
    """Generates an overview of the idea."""
    prompt = f"""Generate a concise and compelling overview of a business idea. Focus on clarity and potential impact.  Incorporate the following data:
    - Industry: {industry}
    - Target Market: {target_market}
    - Problem it Solves: {problem_description}"""

    return _generate_content(prompt, max_tokens=300) 


# Example usage:
overview_data = get_overview(industry="AI-powered education", target_market="K-12 students", problem_description="Lack of personalized learning experiences")
print("Overview:", overview_data['content'])