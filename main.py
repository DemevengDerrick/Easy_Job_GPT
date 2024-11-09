import requests as rq
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from openai import OpenAI
import yaml
import streamlit as st
import os

# set working dir
dirname = os.path.dirname(__file__)

#secrets = yaml.safe_load(open(os.path.join(dirname, "secrets.yaml")))
api_key = st.secrets["api_key"]
client = OpenAI(api_key=api_key)

# get list of jobs from reliefweb
@st.cache_data
def jobs(title):
    url = f"https://api.reliefweb.int/v1/jobs?appname=rwint-user-2878403&profile=list&preset=latest&slim=1&query%5Bvalue%5D={title}&query%5Boperator%5D=AND"
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
                job_description.append(html_text)
                # get suitability from openai
                suitability = job_suitability(html_text, title)
                job_suitability_score.append(suitability)
            else:
                job_description.append(None)
                job_suitability_score.append(None)

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
        soup = BeautifulSoup(response.content, 'html.parser').find('div', class_="rw-article__content").find_all('p')
        text = "\n".join(p.text for p in soup)
        return text
    else:
        return None

# function to rate suitability to the job based on your information.
def job_suitability(html_text, title):
    query = f"{html_text} \n Rate on a scale of 0 to 10 how suitable is the job description to a {title}. just give a number without any text, no comments, just a number"
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
    #secrets = yaml.safe_load(open(dirname, "secrets.yaml"))
    api_key = st.secrets["api_key"]
    client = OpenAI(api_key=api_key)

    df = jobs()

    print(df)









