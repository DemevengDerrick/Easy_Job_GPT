import requests as rq
import pandas as pd
from openai import OpenAI
import yaml

# function to fetch job description from job link
def job_desc_html(html_link):
    response = rq.get(html_link)
    if response.status_code == 200:
        return response.text
    else:
        return None

# function to rate suitability to the job based on your information.
def extract_job_description(html_text):
    query = f"{html_text} \nFrom the HTML text document provided, extract the job description for me. please return just the job description without any extra text from you."
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a kind helpful assistant."},
            {"role": "user", "content": "Who's the best football player in the world?"}
        ]
    )
    # return response
    return response.choices[0].message.content

if __name__ == "__main__":
    secrets = yaml.safe_load(open("D:\WHO\python\job_search\Data_job_search\secrets.yaml"))
    client = OpenAI(api_key=secrets["api_key"])
    #print(secrets["api_key"])

    url = "https://api.reliefweb.int/v1/jobs?appname=rwint-user-0&profile=list&preset=latest&slim=1"
    response = rq.get(url)

    if response.status_code == 200:
        df = pd.json_normalize(response.json()["data"])
        html_link = df["fields.url"][0]

        html_text = job_desc_html(html_link)
        if html_text:
            job_description = extract_job_description(html_text)
            print(job_description)
        else:
            print("Failed to retrieve HTML content.")
    else:
        print("Failed to retrieve job list.")









