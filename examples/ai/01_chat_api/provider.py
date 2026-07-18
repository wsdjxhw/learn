from openai import OpenAI


def generate_reply(user_message: str, system_prompt: str) -> str:
    # provider 层只关心“如何和模型服务交互”，不关心 Web 框架细节。
    client = OpenAI()
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.output_text
