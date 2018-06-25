#!/usr/bin/env python3

from elasticsearch import Elasticsearch
from elasticsearch import helpers
from elasticsearch_dsl import Search, Q
from elasticsearch_dsl.connections import connections
import pymysql
from datetime import timedelta
import datetime


dbconn=pymysql.connect(host='localhost', unix_socket='/var/lib/mysql/mysql.sock', user='root', passwd='', db='db')
dbcursor = dbconn.cursor()

# Elasticsearch connection setup
connections.create_connection(hosts=['ops1'])
client = Elasticsearch([{'host': 'ops1', 'port': 9200, 'timeout': 200, 'http_auth': ('elastic','XXXXXX') }])


# Create this database
#create table daily_response_time (id int not null primary key auto_increment, index_date date, product varchar(255), url varchar(255), resp_time_start_range float, resp_time_end_range float, count float, criteria_avg float, criteria_min float, criteria_max float, criteria_median float);

url_map = {
    "core": ["TakeSurvey",
             "listSurveys.do",
             "surveyFromScratch.do",
             "copyTemplate.do",
             "copyLocalSurvey.do",
             "quickSendII",
             "wizard2SaveQuestion",
             "question.text",
             "quickSurvey.do",
             "quickSurveyII.do",
             "newUser.do",
             "createNewAccount.do"],
    "communities": ["showPanelProject.do",
                    "showPanelProjectHistory.do",
                    "bulkUploadUsers.do",
                    "exportPanelData.do",
                    "newPanelWizardName.do"
                    ],
    "workforce": ["newFlashletPanel.do",
                  "addFlashLetEmployee.do",
                  "bulkUploadMembers.do",
                  "addNewFL360Survey.do",
                  "deployFL360Survey.do",
                  "showFL360SurveyAnalytics.do",
                  "showWeeklyPulseAnalytics.do",
                  "showFlashLetadHocSurveyScoreCard.do"
                  ],
    "cx": ["addCXTouchpoint.do",
           "showTransactionBatch.do",
           "sendCXTransaction.do",
           "showResponseEditor.do",
           "showCXBusinessUnits.do"
           ]
}


time_range = [(0,0.25),(0.25, 0.50), (0.50, 8.0), (8.0, 3600)]
for greater, lesser in time_range:
    print(greater, " ", lesser)

index_date = datetime.date.today() - timedelta(days=1)
index_name= "logstash-" + str(index_date.strftime('%Y.%m.%d'))
print(index_date.strftime('%Y.%m.%d'))
print(index_name)
print(index_date)

for team in url_map:
    print(team)
    for url in url_map[team]:
        print(url)

        for greater, lesser in time_range:
            print(greater, " ", lesser)


            s = Search(using=client, index=index_name, extra={ "size": 10000, "timeout": "20m"} ) \
                .query("match", type="nginx-access")  \
                .query(Q("match", tags="us-nginx-access")) \
                .query(Q("match", request_url=url))

            if(lesser != 3600):
                s=s.filter('range', **{"response_time": {"gte": greater, "lte": lesser}})
            else:
                s=s.filter('range', **{"response_time": {"gte": greater}})

            count=s.count()
            print("url : " , url , " count : " , count)

            s.aggs.metric('response_time', 'avg', field='response_time')
            response = s.execute()
            avg = response.aggregations.response_time.value
            print("url : " , url , " average : " , response.aggregations)

            s.aggs.metric('response_time', 'max', field='response_time')
            response = s.execute(ignore_cache=True)
            max_time = response.aggregations.response_time.value
            print("url : " , url , " max_time : " , max_time)

            s.aggs.metric('response_time', 'min', field='response_time')
            response = s.execute(ignore_cache=True)
            min_time = response.aggregations.response_time.value
            print("url : " , url , " min_time : " , min_time)

            sql = """
                INSERT INTO daily_response_time (index_date, product, url, resp_time_start_range, resp_time_end_range, count, criteria_avg, criteria_min, criteria_max) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            data =(index_date, team, url, greater, lesser, count ,avg, min_time, max_time )
            dbcursor.execute(sql, data)
            dbconn.commit()

dbcursor.close()
dbconn.close()

print("end")
