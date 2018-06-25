#!/usr/bin/env python3
'''
Script will generate a week over week comparison report for each team/product.

'''

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, Index
from elasticsearch_dsl.connections import connections
from datetime import timedelta
import datetime
import jinja2
import collections
import smtplib
from email.message import EmailMessage
import sys

if len(sys.argv) > 1 :
    print("Usage: ./elastic_mean.py <eu|ca|us>")
    if sys.argv[1] in ["eu", "ca", "us"]:
        tag=sys.argv[1] + ".*"
else:
    print("Usage: ./elastic_mean.py <eu|ca|us>")
    sys.exit(2)


env = jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath='.'), extensions=["jinja2.ext.do"])
template=env.get_template('response_time.jinja')

# Elasticsearch connection setup
connections.create_connection(hosts=['elastic1'])
client = Elasticsearch([{'host': 'elastic1', 'port': 9200, 'timeout': 200, 'request_cache': 'false','http_auth': ('elastic','XXXXXXXXXX') }])


maps = collections.OrderedDict({
    "login": ["login.do",
              "showLogin.do"
              ],
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
             "showResponseEditor.do",
             "createNewAccount.do"],
    "communities": ["showPanelProject.do",
                    "showPanelProjectHistory.do",
                    "bulkUploadUsers.do",
                    "exportPanelData.do",
                    "newPanelWizardName.do",
                    "showPanelMemberDashboard.do",
                    "showIdeaboard.do",
                    "showLIveDiscussion.do"
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
           "showCXBusinessUnits.do",
           "cxbusinessunitdashboard.do",
           "editCXTouchpoint.do",
           "showCXSendTouchpointHistory.do",
           "showAddCXBusinessUnit.do",
           "showAddCXTransactions.do"
           ],
    "assessments": ["showAssessment.do",
                    "showAssessmentPortalReport.do",
                    "showAssessmentDashboard.do",
                    "showAssessmentMemberList.do",
                    "exploreAssessment.do",
                    "editPortal.do",
                    "addPortalMember.do",
                    "assessmentMemberImport.do",
                    "createNewAssessmentFromFramework.do"
                    ],
    "forms": ["survey-conversationalsurvey.ConversationalSurveyAPIManager-*",
              "editConveonversationalForm.do",
              "listConversationalForms.do",
              "startConversation.do",
              "survey-angular.forms.theme.FormThemeManager-*"]
})

url_map = collections.OrderedDict()
url_map["login"]=maps["login"]
url_map["core"]=maps["core"]
url_map["communities"]=maps["communities"]
url_map["cx"]=maps["cx"]
url_map["workforce"]=maps["workforce"]
url_map["assessments"]=maps["assessments"]
url_map["forms"]=maps["forms"]

index_date = datetime.date.today() - timedelta(days=1)
to_date = datetime.date.today()

idx = (to_date.weekday()) % 7

this_mon = to_date - timedelta(7+idx)
this_sun = to_date - timedelta(idx + 1)

last_sun = to_date - timedelta(idx+8)
last_mon = to_date - timedelta(idx+14)

window = ((last_mon,last_sun),(this_mon, this_sun))

index_name= "logstash-*"
last_week = str(last_mon) + " to " + str(last_sun)
this_week = str(this_mon) + " to " + str(this_sun)

new_dict = collections.OrderedDict()
for week_start, week_end in window :

    key = str(week_start) + " to " + str(week_end)
    for team in url_map:

        for url in url_map[team]:
            new_dict.setdefault(team, {} ).setdefault(url, {}).setdefault(key, {})
            print("tag is " + tag)

            q = Q('bool', must=[
                Q('match', request_url=url),
                Q('match', tags=tag)
            ])
            print(q)

            s = Search(using=client, index=index_name, extra={"size": 10000, "timeout": "20m"}  ) \
                .query("regexp", nginx_server=tag) \
                .query("match", request_url=url) \
                .filter('range', **{'@timestamp':{"from": week_start, "to": week_end }})

                #.query("match", tags=tag)

                #.query("match", type="nginx-access")

            print(s.to_dict())

            count=s.count()

            s.aggs.metric('response_time', 'avg', field='response_time')
            avg_resp = s.execute(ignore_cache=True)
            avg = avg_resp.aggregations.response_time.value
            print("count is " + str(count) + "\n" + "Average is " + str(avg) + "\n")

            s.aggs.metric('response_time', 'percentiles', field='response_time')
            response = s.execute(ignore_cache=True)
            percentile = response.aggregations.response_time.values

            for value in percentile :
                if value == "75.0":
                    new_dict[team][url][key].update( {value : percentile[value]})
                elif value == "95.0":
                    new_dict[team][url][key].update( {value : percentile[value]})
                elif value == "50.0":
                    new_dict[team][url][key].update( {value : percentile[value]})

            new_dict[team][url][key].update({ "avg": avg })
            new_dict[team][url][key].update({ "count": count })
            if key == this_week and new_dict[team][url][this_week] and new_dict[team][url][last_week] :
                diff = float(new_dict[team][url][this_week]["50.0"]) \
                    - float(new_dict[team][url][last_week]["50.0"])

                new_dict[team][url][key].update({"diff" : diff })


rt = {"test": new_dict}
print(new_dict)

output = template.render(rt)
with open('../index.html', 'w') as f:
    f.write(output);

with open('../index.html') as fp:
    msg = EmailMessage()
    msg.set_content(fp.read(),'html')

msg['Subject'] = '%s - weekly response_time report' % sys.argv[1].upper()
msg['From'] = 'gattu@example.com'
msg['To'] = "admin@example.com"

# Send the message via our own SMTP server.
s = smtplib.SMTP('localhost')
s.send_message(msg)
s.quit()

print("end")


