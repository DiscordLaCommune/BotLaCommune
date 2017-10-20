#!/usr/bin/python3

#Command line parameter:
#1: Discord TOKEN

import discord
import sys
import json
import traceback
import io
import re
import math
import datetime
import time
import asyncio
import random


# Init Discord client
if len(sys.argv) < 1:
	print("Usage: "+sys.argv[0]+" <DISCORD_TOKEN>")
	exit(0)

discord_token = sys.argv[1]
client = discord.Client()

scrutinType = {
	"vote": {
		"duration": 1440,
		"choices": {
			"👍": "D'accord",
			"👎": "Pas d'accord"
		}
	}
}
scrutinVoteInfo = "Vous recevrez une confirmation de vote via message privé. Vous pouvez changer votre vote à tout moment."

def checkEmoji(reaction, emoji):
	e = str(reaction.emoji)
	return e.startswith(emoji)

class Scrutin:
	def __init__(self, question, data, tone, dateEnd):
		self.question = question
		self.dateEnd = dateEnd
		self.data = data
		self.votes = {}
		self.tone = tone
	
	def getMessage(self):
		counter = len(self.votes)
		
		message = "**Scrutin ouvert** jusqu'au "+self.dateEnd.strftime("%d/%m/%y à %H:%M")+"\n"+scrutinVoteInfo+"\n\n"
		if self.question:
			message = message + self.question+"\n\n"
		for c,t in self.data.get("choices", {}).items():
			message = message + c+self.tone+" : "+t+"\n\n"
		message = message + "🤷"+self.tone+" : Abstention\n\n"
		message = message + "Participation : " + str(counter)
		if counter > 1:
			message = message + " personnes."
		else:
			message = message + " personne."
		
		return message
	
	def setVote(self, userId, emoji):
		self.votes[userId] = emoji
	
	def checkTime(self, t):
		return t > self.dateEnd

ongoingVotes = {}

@client.event
async def on_ready():
	print("* Bot "+client.user.name+" logged successfully")

	prevTime = time.time()
	while True:
		currTime = time.time()
		sleepDuration = 60 - (currTime - prevTime)
		prevTime = currTime
		if sleepDuration > 0:
			await asyncio.sleep(sleepDuration)
		
		with open('backup.json', 'w') as outfile:
			data = {}
			data["scrutins"] = []
			for s,scrutin in ongoingVotes.items():
				data["scrutins"].append({
					"question": scrutin.question,
					"data": scrutin.data,
					"votes": scrutin.votes,
					"dateEnd": scrutin.dateEnd.time().isoformat(),
					"tone": scrutin.tone,
					"serverId": s[0],
					"channelId": s[1],
					"messageId": s[2]
				})
		
			json.dump(data, outfile)
			
		toDelete = set()
		
		for s,scrutin in ongoingVotes.items():
			if ongoingVotes[s].checkTime(datetime.datetime.now() + datetime.timedelta(minutes=1)):
				toDelete.add(s)
				
				serv = client.get_server(s[0])
				if not serv:
					break
				chan = serv.get_channel(s[1])
				if not chan:
					break
				
				msg = await client.get_message(chan, s[2])
				if not msg:
					break
				
				voteCounter = {}
				for uid,v in ongoingVotes[s].votes.items():
					if v in voteCounter:
						voteCounter[v] = voteCounter[v] + 1
					else:
						voteCounter[v] = 1
				
				text = "**Scrutin fermé.**\n\n"
				if ongoingVotes[s].question:
					text = text + ongoingVotes[s].question+"\n\n"
				for e,t in ongoingVotes[s].data.get("choices",{}).items():
					text = text + e+ongoingVotes[s].tone+" : "+str(voteCounter.get(e, 0))+"\n\n"
				text = text + "🤷"+ongoingVotes[s].tone+" : "+str(voteCounter.get("🤷", 0))+"\n\n"
				
				text = text + "Participation : "+str(len(ongoingVotes[s].votes))
				if len(ongoingVotes[s].votes) > 1:
					text = text + " personnes."
				else:
					text = text + " personne."
				
				await client.clear_reactions(msg)
				await client.edit_message(msg, text)
		
		for k in toDelete:
			del(ongoingVotes[k])
		
@client.event
async def on_message(message):
	try:
		if not message.server:
			return
		if message.author.bot:
			return
		if message.content.find(client.user.mention+" ") != 0:
			return
		
		skinTone = random.choice(["", "🏻", "🏼", "🏽", "🏾", "🏿"])
		
		msgContent = message.content[len(client.user.mention+" "):].strip()
		msgKeywords = msgContent.split(" ")
		if len(msgKeywords) == 0:
			return
		
		if msgKeywords[0].strip() == "help":
			text = "**Commandes:**\n\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" vote <texte>`` : lancer un scrutin « pour ou contre » d'une durée de un jour. Remplacez ``<texte>`` par la question du vote.\n"
			await client.send_message(message.channel, text)
			return
		
		mode = None
		if msgKeywords[0].strip() == "vote":
			mode = "vote"
		elif msgKeywords[0].strip() == "quickvote":
			mode = "vote"
		
		if mode:
			chan = message.channel
			for c in message.server.channels:
				if c.name == "vote_populaire":
					chan = c
					break
			
			if not chan:
				return
			
			question = " ".join(msgKeywords[1:])
			dateEnd = datetime.datetime.now() + datetime.timedelta(minutes=scrutinType[mode].get("duration", 1))
			scrutin = Scrutin(question, scrutinType[mode], skinTone, dateEnd)
			
			voteMsg = await client.send_message(chan, scrutin.getMessage())
			voteKey = (voteMsg.server.id, voteMsg.channel.id, voteMsg.id)
			
			ongoingVotes[voteKey] = scrutin
			for e in scrutinType[mode].get("choices", {}):
				await client.add_reaction(voteMsg, e+skinTone)
			await client.add_reaction(voteMsg, "🤷"+skinTone)
			await client.pin_message(voteMsg)
			await client.delete_message(message)
	except:
		await client.send_message(message.channel, "Oups...")
		print(traceback.format_exc())

@client.event
async def on_reaction_add(reaction, user):
	try:
		if not reaction.message.server:
			return
		if user.bot:
			return
		
		voteKey = (reaction.message.server.id, reaction.message.channel.id, reaction.message.id)
		
		if voteKey not in ongoingVotes:
			return
		if ongoingVotes[voteKey].checkTime(datetime.datetime.now()):
			return
		
		emoji = None
		if checkEmoji(reaction, "🤷"):
			emoji = "🤷"
		else:
			for e in ongoingVotes[voteKey].data.get("choices", {}):
				if checkEmoji(reaction, e):
					emoji = e
					break
		
		if emoji:
			ongoingVotes[voteKey].setVote(user.id, emoji)
			await client.edit_message(reaction.message, ongoingVotes[voteKey].getMessage())
			await client.send_message(user, "Votre vote a été enregistré. Vous avez voté "+emoji+". Si vous avez déjà participé à ce scrutin, votre vote à simplement été changé.")
		
		await client.remove_reaction(reaction.message, reaction.emoji, user)
		
	except:
		await client.send_message(reaction.message.channel, "Oups...")
		print(traceback.format_exc())

client.run(discord_token)
