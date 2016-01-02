from django.shortcuts import render
from django.core.signing import Signer
from django.core import signing
from django.http import HttpResponse
from django.http import HttpRequest
from django.http import HttpResponseRedirect

import logging
from httplib2 import Http
import json



# Create your views here.

def welcome(request):
    return render(request, 'frontend/welcome.html')

def dashboard(request):
    parser = Http()
    signer = Signer('secretKey')
    ACCESS_TOKEN = request.COOKIES.get("ACCESSTOKEN")
    if ACCESS_TOKEN:
        accesstoken = signer.unsign(ACCESS_TOKEN)

    logging.info('DECRYPTED TOKEN - ' + accesstoken)

    resp, content = parser.request("https://www.googleapis.com/oauth2/v1/userinfo?access_token={accessToken}".format(accessToken= accesstoken))

    logging.info(content)
    user = json.loads(content)
    logging.info(user)

    resp, content = parser.request("http://localhost:8080/services/dashboard",headers={'Cookie':"ACCESSTOKEN="+ACCESS_TOKEN})

    dashboardData = content

    return render(request, 'frontend/newdash.html',{"username": user["name"],"userimg": user["picture"], "dashboardData": dashboardData})