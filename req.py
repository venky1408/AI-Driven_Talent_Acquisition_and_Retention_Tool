import requests
import json

url = "https://retention-model1-db00095f4cea.herokuapp.com/predict"
headers = {"Content-Type": "application/json"}
data = {
  "satisfaction_level": 0.11,
  "last_evaluation": 0.88,
  "number_project": 5,
  "average_monthly_hours": 272,
  "time_spend_company": 4,
  "work_accident": 0,
  "promotion_last_5years": 0,
  "Department": "sales",
  "salary": "medium"
}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(response.json())