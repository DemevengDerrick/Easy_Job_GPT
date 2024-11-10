import main
import streamlit as st
import docs
from openai import OpenAI
import yaml
import os

# set working dir
dirname = os.path.dirname(__file__)
img = os.path.join(dirname, "img/image.png")
# Page title
col1, mid, col2 = st.columns([1,1,20])
with col1:
    st.image(img, width=73)
with col2:
    st.title('EASY JOB GPT') 

st.write("Welcome to Easy Job GPT, your personal job application assistant. With Easy Job GPT, you can search for job by job tible, extact job describtion, upload your CV and generate a custom Motivation letter in alignemnet with the Job offer.")

title = st.text_input(label="Search Job Title", value="GIS")

st.write("Select a job offer in the table below by selecting the row")
df = main.jobs(title)

event = st.dataframe(df, 
             selection_mode="single-row",
             hide_index = True, 
             on_select="rerun")

try:
    selection = event.selection.rows
    if selection is not None:
        job_description = df.iloc[selection]["job_description"].item()
        st.text_area(value = job_description, label= "Job Description", height=500)
except:
    pass

# selection = event.selection.rows
# url = df.iloc[selection]["fields.url"].item()
# st.write(url)

# Upload and read CV
uploaded_file = st.file_uploader("Upload your CV in word format")
if uploaded_file is not None:
    # To convert to a string based IO:
    text = docs.extract_text_from_docx(uploaded_file)
    # To read file as string:
    st.text_area(label = "CV Preview", value=text, key = 1, height=500)


# secrets = yaml.safe_load(open(os.path.join(dirname, "secrets.yaml")))
# client = OpenAI(api_key=secrets["api_key"])

api_key = st.secrets["api_key"]
client = OpenAI(api_key=api_key)

def motivation_letter():
    # Generate motivation letter
    query1 = f"{job_description} \n based on this job description"
    query2 = f"{text} \n and this CV, write a motivation letter that matches my CV."
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a kind helpful assistant."},
            {"role": "user", "content": query1},
            {"role": "user", "content": query2}
        ]
    )
    # return response
    motivation_letter_placeholder.text_area(value = response.choices[0].message.content, label = "Motivation Letter", key = 2, height=500)

st.button("Generate Motivation Letter", on_click=motivation_letter, icon="🔥")
# Placeholder for motivation letter
motivation_letter_placeholder = st.container()

st.caption(body="Derrick Demeveng | linkedIn : www.linkedin.com/in/demeveng-derrick")







