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
		"instructions": True,
		"choices": [
			{ "emoji": "👎", "text": "Pas d'accord" },
			{ "emoji": "🤷", "text": "Neutre" },
			{ "emoji": "👍", "text": "D'accord" }
		]
	},
	"weekvote": {
		"duration": 10080,
		"instructions": True,
		"choices": [
			{ "emoji": "👎", "text": "Pas d'accord" },
			{ "emoji": "🤷", "text": "Neutre" },
			{ "emoji": "👍", "text": "D'accord" }
		]
	},
	"hvote": {
		"duration": 60,
		"instructions": True,
		"choices": [
			{ "emoji": "👎", "text": "Pas d'accord" },
			{ "emoji": "🤷", "text": "Neutre" },
			{ "emoji": "👍", "text": "D'accord" }
		]
	},
	"election": {
		"duration": 60,
		"instructions": False,
		"choices": [
			{ "emoji": "😡", "text": "Pas d'accord" },
			{ "emoji": "😒", "text": "Plutôt pas d'accord" },
			{ "emoji": "😶", "text": "Neutre" },
			{ "emoji": "😊", "text": "Plutôt d'accord" },
			{ "emoji": "😍", "text": "D'accord" }
		]
	},
	"livevote": {
		"duration": -1,
		"instructions": True,
		"choices": [
			{ "emoji": "👎", "text": "Pas d'accord" },
			{ "emoji": "🤷", "text": "Neutre" },
			{ "emoji": "👍", "text": "D'accord" }
		]
	}
}
scrutinVoteInfo = "Vous pouvez voter en cliquant sur une « réaction ». Vous recevrez alors une confirmation de vote via message privé. Vous pouvez changer votre vote à tout moment."

emojiWithTone = ["👎", "🤷", "👍"]

def checkEmoji(reaction, emoji):
	e = str(reaction.emoji)
	return e.startswith(emoji)

def applyTone(emoji, tone):
	if emoji in emojiWithTone:
		return emoji+tone
	else:
		return emoji

class Scrutin:
	def __init__(self, question, data, tone, dateStart):
		self.question = question
		self.dateStart = dateStart
		self.data = data
		self.votes = {}
		self.tone = tone
	
	def getMessage(self):
		counter = len(self.votes)
		
		voteCounter = {}
		for uid,v in self.votes.items():
			if v in voteCounter:
				voteCounter[v] = voteCounter[v] + 1
			else:
				voteCounter[v] = 1
		
		message = ""
		if self.data.get("instructions", True):
			if self.data.get("duration", -1) < 0:
				message = message + "**Scrutin live**\n"
			else:
				dateEnd = self.dateStart + datetime.timedelta(minutes=self.data.get("duration", -1))
				message = message + "**Scrutin ouvert** jusqu'au "+dateEnd.strftime("%d/%m/%y à %H:%M")+"\n"
			
			message = message + scrutinVoteInfo+"\n\n"
		
		if self.question:
			message = message + self.question+"\n"
		
		if self.data.get("instructions", True):
			message = message + "\n"
			for c in self.data.get("choices", []):
				if self.data.get("duration", -1) < 0:
					message = message + applyTone(c["emoji"], self.tone)+" : "+c["text"]+" ("+str(voteCounter.get(c["emoji"], 0))+")\n\n"
				else:
					message = message + applyTone(c["emoji"], self.tone)+" : "+c["text"]+"\n\n"
		
		message = message + "Participation : " + str(counter)
		if counter > 1:
			message = message + " personnes."
		else:
			message = message + " personne."
		
		return message
	
	def setVote(self, userId, emoji):
		self.votes[userId] = emoji
	
	def getVote(self, userId):
		return self.votes.get(userId, None)
	
	def checkTime(self, t):
		if self.data.get("duration", -1) < 0:
			return False
		else:
			dateEnd = self.dateStart + datetime.timedelta(minutes=self.data.get("duration", -1))
			return t > dateEnd

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
					"dateStart": scrutin.dateStart.time().isoformat(),
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
				
				try:
					msg = await client.get_message(chan, s[2])
				
					voteCounter = {}
					for uid,v in ongoingVotes[s].votes.items():
						if v in voteCounter:
							voteCounter[v] = voteCounter[v] + 1
						else:
							voteCounter[v] = 1
					
					text = "**Scrutin fermé.**\n\n"
					if ongoingVotes[s].question:
						text = text + ongoingVotes[s].question+"\n\n"
					for c in ongoingVotes[s].data.get("choices",[]):
						text = text + applyTone(c["emoji"], ongoingVotes[s].tone) +" : "+str(voteCounter.get(c["emoji"], 0))+"\n\n"
					
					text = text + "Participation : "+str(len(ongoingVotes[s].votes))
					if len(ongoingVotes[s].votes) > 1:
						text = text + " personnes."
					else:
						text = text + " personne."
					
					await client.clear_reactions(msg)
					await client.edit_message(msg, text)
				except discord.errors.NotFound:
					pass
		
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
		
		msgContent = message.content[len(client.user.mention+" "):].strip()
		msgKeywords = msgContent.split(" ")
		if len(msgKeywords) == 0:
			return
		
		cmd = msgKeywords[0].strip()
		
		if cmd == "help":
			text = "**Commandes:**\n\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" vote <texte>`` : lancer un scrutin « pour ou contre » d'une durée de un jour. Remplacez ``<texte>`` par la question à vote.\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" hvote <texte>`` : lancer un scrutin « pour ou contre » d'une durée de une heure. Remplacez ``<texte>`` par la question à vote.\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" weekvote <texte>`` : lancer un scrutin « pour ou contre » d'une durée de une semaine. Remplacez ``<texte>`` par la question à vote.\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" electiondesc`` <texte> : Afficher les instructions pour un scrutin à base de jugement. Remplacez ``<texte>`` par une description des modalités.\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" election <texte>`` : lancer un scrutin de jugement d'une durée de un jour. Remplacez ``<texte>`` par la question à vote.\n"
			text = text + "``@"+client.user.name+"#"+client.user.discriminator+" livevote <texte>`` : lancer un scrutin live qui affiche les résultats en directe. Remplacez ``<texte>`` par la question à vote.\n"
			await client.send_message(message.channel, text)
			return
		
		elif cmd == "electiondesc":
			text = "**Comment fonctionne ce vote ?**\n\n"+scrutinVoteInfo+"\n\n"
			
			question = " ".join(msgKeywords[1:])
			if len(question):
				text = text + question+"\n\n"
			
			for c in scrutinType["election"].get("choices", []):
				text = text + applyTone(c["emoji"], "")+" : "+c["text"]+"\n\n"
			
			await client.send_message(message.channel, text)
			return
		
		elif cmd in scrutinType:
			skinTone = random.choice(["", "🏻", "🏼", "🏽", "🏾", "🏿"])
			
			chan = message.channel
			
			if not chan:
				return
			
			question = " ".join(msgKeywords[1:])
			scrutin = Scrutin(question, scrutinType[cmd], skinTone, datetime.datetime.now())
			
			voteMsg = await client.send_message(chan, scrutin.getMessage())
			voteKey = (voteMsg.server.id, voteMsg.channel.id, voteMsg.id)
			
			ongoingVotes[voteKey] = scrutin
			for c in scrutinType[cmd].get("choices", []):
				await client.add_reaction(voteMsg, applyTone(c["emoji"], skinTone))
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
		for c in ongoingVotes[voteKey].data.get("choices", []):
			if checkEmoji(reaction, c["emoji"]):
				emoji = c["emoji"]
				break
		
		if emoji:
			lastVote = ongoingVotes[voteKey].getVote(user.id)
			ongoingVotes[voteKey].setVote(user.id, emoji)
			await client.edit_message(reaction.message, ongoingVotes[voteKey].getMessage())
			if lastVote == emoji:
				await client.send_message(user, "Vous avez déjà voté "+emoji+" à la question suivante : "+ongoingVotes[voteKey].question)
			elif lastVote:
				await client.send_message(user, "Votre vote a été changé de "+lastVote+" vers "+emoji+" pour la question suivante : "+ongoingVotes[voteKey].question)
			else:
				await client.send_message(user, "Votre vote a été enregistré. Vous avez voté "+emoji+" à la question suivante : "+ongoingVotes[voteKey].question)
		
		await client.remove_reaction(reaction.message, reaction.emoji, user)
		
	except:
		await client.send_message(reaction.message.channel, "Oups...")
		print(traceback.format_exc())

@client.event
async def on_reaction_remove(reaction, user):
	try:
		if not reaction.message.server:
			return
		if user.id != client.user.id:
			return
		
		voteKey = (reaction.message.server.id, reaction.message.channel.id, reaction.message.id)
		
		if voteKey not in ongoingVotes:
			return
		if ongoingVotes[voteKey].checkTime(datetime.datetime.now()):
			return
		
		await client.add_reaction(reaction.message, reaction.emoji)
		
	except:
		await client.send_message(reaction.message.channel, "Oups...")
		print(traceback.format_exc())

client.run(discord_token)
