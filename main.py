import requests as rq
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from openai import OpenAI
import yaml

# get list of jobs from reliefweb
def jobs():
    url = "https://api.reliefweb.int/v1/jobs?appname=rwint-user-0&profile=list&preset=latest&slim=1"
    response = rq.get(url)
    if response.status_code == 200:
        # get the result in a dataframe
        df = pd.json_normalize(response.json()["data"])
        # empty list to hold job descriptions
        job_description = list()
        job_suitability_score = list()
        for link in df["fields.url"]:
        #html_link = df["fields.url"]
            html_text = job_desc_html(link)
            if html_text:
                # extract jub description
                soup = BeautifulSoup(html_text, 'html.parser').find('div', class_="rw-article__content").find_all('p')
                job_description.append(soup)
                # get suitability from openai
                suitability = job_suitability(soup)
                job_suitability_score.append(suitability)
            else:
                job_description.append(None)
        df["job_description"] = np.array(job_description)
        df["suitability"] = np.array(job_suitability_score)
        # return dataframe
        return df
    else:
        return None

# function to fetch job description from job link
def job_desc_html(html_link):
    response = rq.get(html_link)
    if response.status_code == 200:
        return response.content
    else:
        return None

# function to rate suitability to the job based on your information.
def job_suitability(html_text):
    query = f"{html_text} \n Rate on a scale of 0 to 10 how suitable is the job description to a GIS, Data Analyst and Data Manager"
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a kind helpful assistant."},
            {"role": "user", "content": query}
        ]
    )
    # return response
    return response.choices[0].message.content

if __name__ == "__main__":
    secrets = yaml.safe_load(open("D:\WHO\python\job_search\Data_job_search\secrets.yaml"))
    client = OpenAI(api_key=secrets["api_key"])

    df = jobs()

    print(df)









