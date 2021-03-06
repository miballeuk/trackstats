from __future__ import division
from django.shortcuts import render
from django.http import HttpResponse
import datetime
from datetime import date, timedelta
import time
import json
import os
from django.core.signing import Signer
import ssl
import logging

import requests
from pprint import pprint


EPOCH_START = datetime.datetime.utcfromtimestamp(0)


signer = Signer('secretKey')

errorMessage1 = "We can't process your request right now, please try again later."
#errorMessage2 = "Invalid Data Format. Potentially missing Google Fit data."

# Converts time ...
def timestamp_converter_nanos(date_time):
	timestamp_pattern = '%Y-%m-%dT%H:%M:%S.00Z'
	epoch = int(time.mktime(time.strptime(date_time, timestamp_pattern))) * 1000000000
	return epoch

# Converts time from milliseconds to nanoseconds
def millis_converter_nanos(milliseconds):
	return milliseconds * 1000000

# Returns average stats about last month for dashboard
def dashboard(request):
	try:
		logging.info('[Services][Dashboard] Request Start')
		oauthAccessToken = signer.unsign(request.COOKIES.get("ACCESSTOKEN"))

		# Start-End times in timestamp format
		rawEndTime = datetime.datetime.now()
		endTime = rawEndTime.strftime('%Y-%m-%dT%H:%M:%S.00Z')

		startTime = (rawEndTime - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S.00Z')

		logging.info('[Services][Dashboard][StartTime] Start: %s, End: %s', startTime, endTime)
		# Start-End times in epoch nanoseconds time format
		endTimeNanos = timestamp_converter_nanos(endTime)
		startTimeNanos = timestamp_converter_nanos(startTime)

		logging.info('[Services][Dashboard][StartTime] StartNanos: %d, EndNanos: %d', startTimeNanos, endTimeNanos)

		epochStartTime = EPOCH_START.strftime('%Y-%m-%dT%H:%M:%S.00Z')
		# Get summary data about last month for dashboard
		weight = get_weight(oauthAccessToken, timestamp_converter_nanos(epochStartTime), endTimeNanos)
		calories = get_calories(oauthAccessToken ,startTimeNanos, endTimeNanos, False)
		distance = get_detailed_distance(oauthAccessToken, startTimeNanos, endTimeNanos, False)
		sesLastMonth = get_sessions(oauthAccessToken,startTime,endTime, False)
		nSessions = sesLastMonth

		ses_all = get_sessions(oauthAccessToken,epochStartTime,endTime, True)
		sessionData = ses_all[1]

		dashboardSummary = {"calories": round(calories,0), "distance": round(distance/1000,2), "nsessions": nSessions, "weight": weight, "sessions": sessionData}

		logging.info('[Services][Dashboard] Request End')

		response = HttpResponse()
		response.write(dashboardSummary)
		return response

	except:
		return HttpResponse(errorMessage1)

# This function returns all sessions for a given time interval
# @request
# @sTime,eTime - strings from timestamps (in proper format!)
# @boo : boolean parameter - True to return sessions dataset - False for total session number only
# default return value is zero and empty set
def get_sessions(token,sTime,eTime, boo):
	try:
		logging.info('[Services][GetSessions] Function start')
		session_params  = {'startTime':sTime , 'endTime': eTime , 'access_token' : token  }

		url = "https://www.googleapis.com/fitness/v1/users/me/sessions"
		r = requests.get(url, params = session_params )
		data = r.json()
		logging.info('[Services][GetSessions] JSON Resp: %s', str(r.json()).encode('utf-8'))

		sessions = data["session"]

		logging.info('[Services][GetSessions] Function end')

		if boo is True:
			return [len(sessions), sessions]
		else:
			return len(sessions)

	except KeyError:
		if boo is True:
			return [0, []]
		else:
			return 0
	except:
		return HttpResponse(errorMessage1)



# Function that returns the last weight value or a string that promts user to submit weight.
# @request
# @startTimeNanos,endTimeNanos - epoch time in nanoseconds
def get_weight(token,startTimeNanos,endTimeNanos):
	logging.info('[Services][GetWeight] Function start')
	try:
		session_params  = {'access_token' : token  }

		last_weight_dataSourceId = "derived:com.google.weight:com.google.android.gms:merge_weight"
		last_weight_datasetId = "0-" + str(endTimeNanos)
		weightOptions = {'userId': 'me' , 'dataSourceId': last_weight_dataSourceId , 'datasetId': last_weight_datasetId }

		last_weight_url = "https://www.googleapis.com/fitness/v1/users/{userId}/dataSources/{dataSourceId}/datasets/{datasetId}".format(**weightOptions)
		logging.info('[Services][GetWeight] LastWeigth URL: %s', last_weight_url)
		r = requests.get(last_weight_url, params = session_params )

		logging.info('[Services][GetWeight] JSON Resp: %s', r.json())

		weightData = r.json()["point"]
		weight = "Submit Weight!"

		for it in weightData:
			weight = it["value"][0]["fpVal"]

		logging.info('[Services][GetWeight] Function end - Return %d', weight)

		return weight
	except KeyError:
		return 0
	except:
		return HttpResponse(errorMessage1)


# Function that returns calories data on a given time interval.
# @request
# @startTimeNanos,endTimeNanos - epoch time in nanoseconds
# @boo : boolean parameter - True to return the dataset to be plotted - False for total calories only
def get_calories(token,startTimeNanos,endTimeNanos, boo):
	try:
		logging.info('[Services][GetCalories] Function start')
		session_params  = {'access_token' : token  }

		# Set parameters for request
		datasetId = str(startTimeNanos) + "-" + str(endTimeNanos)

		# Last month calories summary request
		dataSourceId = "derived:com.google.calories.expended:com.google.android.gms:from_activities"
		options = {'userId': 'me' , 'dataSourceId': dataSourceId , 'datasetId': datasetId }
		url = "https://www.googleapis.com/fitness/v1/users/{userId}/dataSources/{dataSourceId}/datasets/{datasetId}".format(**options)

		r = requests.get(url, params = session_params )

		logging.info('[Services][GetCalories] JSON Resp: %s', r.json())

		data = r.json()["point"]
		totalCalories = 0

		for it in data:
			totalCalories += it["value"][0]["fpVal"]

		logging.info('[Services][GetCalories] Function end')

		if boo is True:
			return [totalCalories, data]
		else:
			return totalCalories
	except KeyError:
		if boo is True:
			return [0, []]
		else:
			return 0
	except:
		return HttpResponse(errorMessage1)


# Function that returns location data on a given time interval.
# @request
# @startTimeNanos,endTimeNanos - epoch time in nanoseconds
# data is formatted and exported in format requested by fronted.
def get_location(token,startTimeNanos,endTimeNanos):
	try:
		logging.info('[Services][GetLocation] Function start')
		session_params  = {'access_token' : token }

		# Set parameters for request
		datasetId = str(startTimeNanos) + "-" + str(endTimeNanos)

		# Last month calories summary request
		dataSourceId = "derived:com.google.location.sample:com.google.android.gms:merge_location_samples"
		options = {'userId': 'me' , 'dataSourceId': dataSourceId , 'datasetId': datasetId }
		url = "https://www.googleapis.com/fitness/v1/users/{userId}/dataSources/{dataSourceId}/datasets/{datasetId}".format(**options)

		r = requests.get(url, params = session_params )

		logging.info('[Services][GetLocation] JSON Resp: %s', r.json())

		rawData = r.json()["point"]

		# com.google.location.sample	The user's current location.
		# Permission: Location
		# List items in ["value"]
		# [0] : latitude (float : degrees)
		# [1] : longitude (float : degrees)
		# [2] : accuracy (float : meters)
		# [3] : altitude (float : meters)

		data = []
		for it in rawData:
			data.append([it["value"][0]["fpVal"], it["value"][1]["fpVal"]])

		logging.info('[Services][GetCalories] Function end')

		# data format:
		# [[lat,lon], ...]
		return data

	except KeyError:
		return []
	except:
		return HttpResponse(errorMessage1)


# Function that returns distance data on a given time interval - incomplete.
# @request
# @startTimeNanos,endTimeNanos - epoch time in nanoseconds
# @boo : boolean parameter - True to return the dataset to be plotted - False for total distance only
def get_detailed_distance(token,startTimeNanos,endTimeNanos, boo):
	try:
		logging.info('[Services][GetDetailedDistance] Function start')
		# Set parameters for request
		datasetId = str(startTimeNanos) + "-" + str(endTimeNanos)

		# Last month calories summary request
		dataSourceId = "derived:com.google.distance.delta:com.google.android.gms:merge_distance_delta"
		options = {'userId': 'me' , 'dataSourceId': dataSourceId , 'datasetId': datasetId }
		url = "https://www.googleapis.com/fitness/v1/users/{userId}/dataSources/{dataSourceId}/datasets/{datasetId}".format(**options)

		session_params  = {'access_token' : token }

		r = requests.get(url, params = session_params )

		logging.info('[Services][GetDetailedDistance] JSON Resp: %s', r.json())

		data = r.json()["point"]

		totalDistance = 0
		for it in data:
			totalDistance += it["value"][0]["fpVal"]
			# data to frontend documentation
			# data is a list of json objects
			# to access them use the following:
			# x = it["endTimeNanos"]
			# f(x) = it["value"][0]["fpVal"]

		logging.info('[Services][GetDetailedDistance] Function end')

		if boo is True:
			return [totalDistance, data]
		else:
			return totalDistance
	except KeyError:
		if boo is True:
			return [0, []]
		else:
			return 0
	except:
		return HttpResponse(errorMessage1)

# Function that returns speed data on a given time interval - incomplete.
# @request
# @startTimeNanos,endTimeNanos - epoch time in nanoseconds
# @boo : boolean parameter - True to return the dataset to be plotted - False for average distance only
def get_detailed_speed(token,startTimeNanos,endTimeNanos, boo):
	try:
		logging.info('[Services][GetDetailedDSpeed] Function start')
		# Set parameters for request
		datasetId = str(startTimeNanos) + "-" + str(endTimeNanos)

		# Last month calories summary request
		dataSourceId = "derived:com.google.speed:com.google.android.gms:merge_speed"
		options = {'userId': 'me' , 'dataSourceId': dataSourceId , 'datasetId': datasetId }
		url = "https://www.googleapis.com/fitness/v1/users/{userId}/dataSources/{dataSourceId}/datasets/{datasetId}".format(**options)

		session_params  = {'access_token' : token }

		if boo is True:
			r = requests.get(url, params = session_params )

			logging.info('[Services][GetDetailedSpeed] JSON Resp: %s', r.json())

			data = r.json()["point"]

		totalDistance = get_detailed_distance(token,startTimeNanos,endTimeNanos, False)
		timeInterval = (endTimeNanos - startTimeNanos)/1000000000
		avgspeed = totalDistance/timeInterval

		logging.info('[Services][GetDetailedDSpeed] Function end')

		if boo is True:
			return [avgspeed, data]

		else:
			return avgspeed
	except KeyError:
		if boo is True:
			return [0, []]

		else:
			return 0
	except:
		return HttpResponse(errorMessage1)




# Function that gives the information required to create the session/workout page for the user (plot_data and summary).
# The query from front end should include starttime and endtime in milliseconds
# --------------> needs to be implemented !!
# which we will need to convert them in nanoseconds.
def workout(request):

# def workout(request, startTime, endTime):
# ?startTime=1448983095955&endTime=1548987127050
# adding the above did not give the values to the script - how to give them?

	try:
		logging.info('[Services][Workout] Request start')
		oauthAccessToken = signer.unsign(request.COOKIES.get("ACCESSTOKEN"))
		# oauthAccessToken = "ya29.WgK0DSor04y7F7phLwE4DOzE_Pwmuvr_0sAnl9QXQcf0WQ7DG_PwU0YZCl7CQ9bNyppm"

		# Fixed Time issue input
		# times are given within the get request
		# example url for previously hardcoded times is:
		# ?startTime=1451493869506&endTime=1451494113312
		# ?startTime=1451494137234&endTime=1451494830941
		startTime = request.GET["startTime"]
		endTime = request.GET["endTime"]

		startTime = int(startTime)
		endTime = int(endTime)

		# hardcoded times - we need them from the front end from users choice !!!
		# startTime = 1448983095955
		# endTime = 1548987127050

		# Start - End times in epoch nanoseconds time format
		endTimeNanos = millis_converter_nanos(endTime)
		startTimeNanos = millis_converter_nanos(startTime)

		logging.info(endTimeNanos)
		logging.info(startTimeNanos)

		# datasetId = str(startTimeNanos) + "-" + str(endTimeNanos)

		# create deliverables

		# 0 item in list is total distance
		# 1 item in list is data dictionary

		speed = get_detailed_speed(oauthAccessToken, startTimeNanos, endTimeNanos, True)
		calories = get_calories(oauthAccessToken, startTimeNanos, endTimeNanos, True)

		# only data no total/average here
		location = get_location(oauthAccessToken, startTimeNanos, endTimeNanos)

		average = {'avgspeed': round(speed[0],4), 'totalcalories': round(calories[0],2)}

		data = []
		data.append(speed[1])
		data.append(calories[1])
		data.append(location)

		logging.info('[Services][Workout] Request end')

		results = [average, data]

		response = HttpResponse()
		response.write(results)

		return response

	except:
		return HttpResponse(errorMessage1)

"""
Documentation for front end:
Workout Page:
Results are a list
[0] is for workout summary
[1] is for detailed data to plot_data
[1][0] is for speed data    > spoken with Sandeep about format
[1][1] is for calories data > spoken with Sandeep about format
[1][2] is for location data > in format Manos wants them to plot map route
"""