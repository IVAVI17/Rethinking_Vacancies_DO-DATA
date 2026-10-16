
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, GroqError


# ---------------------------------------
# 1. Find project files
# ---------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Load API key from .env
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY or API_KEY == "PASTE_YOUR_NEW_GROQ_KEY_HERE":
    raise SystemExit(
        "ERROR: GROQ_API_KEY is missing. "
        "Please add your API key to the .env file."
    )


# ---------------------------------------
# 2. Connect to Groq Cloud
# ---------------------------------------

client = Groq(
    api_key=API_KEY,
    timeout=30.0
)

MODEL = "openai/gpt-oss-20b"


# ---------------------------------------
# 3. Load the AI system prompt
# ---------------------------------------

prompt_path = BASE_DIR / "system_prompt.txt"

if not prompt_path.exists():
    raise SystemExit(
        "ERROR: system_prompt.txt was not found."
    )

SYSTEM_PROMPT = prompt_path.read_text(
    encoding="utf-8"
)


# ---------------------------------------
# 4. Send a request to Groq AI
# ---------------------------------------

def analyse_property_request(user_request):

    completion = client.chat.completions.create(
        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\n\nIMPORTANT: Return your response "
                      "as a valid JSON object only. "
                      "Do not include Markdown formatting."
                )
            },
            {
                "role": "user",
                "content": user_request
            }
        ],

        response_format={
            "type": "json_object"
        },

        temperature=0.2,

        max_completion_tokens=3000
    )

    answer = completion.choices[0].message.content

    if not answer:
        raise ValueError(
            "Groq returned an empty answer."
        )

    # Convert AI response into Python dictionary
    result = json.loads(answer)

    return result


# ---------------------------------------
# 5. Interactive testing
# ---------------------------------------

def main():

    print("\n" + "=" * 55)
    print("       DORTMUND SPACEMATCH AI")
    print("       Groq Cloud Property Search Tester")
    print("=" * 55)

    print("\nAI model:", MODEL)
    print("Type a property request to test the AI.")
    print("Type 'exit' to quit.\n")

    while True:

        user_request = input(
            "\nDescribe your ideal workspace:\n> "
        ).strip()

        if user_request.lower() in ["exit", "quit"]:
            print("\nGoodbye!")
            break

        if not user_request:
            print("Please enter a request.")
            continue

        print("\nAI is analysing your request...\n")

        try:

            result = analyse_property_request(
                user_request
            )

            print("\n" + "=" * 55)
            print("EXTRACTED SEARCH FILTERS")
            print("=" * 55)

            print(
                json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False
                )
            )

            print("=" * 55)

        except GroqError as error:

            print("\nGroq API error:")
            print(error)

        except json.JSONDecodeError:

            print(
                "\nThe AI returned invalid JSON. "
                "Please try again."
            )

        except Exception as error:

            print("\nUnexpected error:")
            print(error)


# ---------------------------------------
# 6. Run the program
# ---------------------------------------

if __name__ == "__main__":
    main()
