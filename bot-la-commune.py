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
import dateutil.parser
import operator

# Init Discord client
if len(sys.argv) < 1:
	print("Usage: "+sys.argv[0]+" <DISCORD_TOKEN>")
	exit(0)

discord_token = sys.argv[1]
client = discord.Client()

scrutinType = {
	"default": {
		"duration": 1440,
		"instructions": True,
		"live": False,
		"choices": [
			{ "emoji": "👎", "text": "Pas d'accord" },
			{ "emoji": "🤷", "text": "Neutre" },
			{ "emoji": "👍", "text": "D'accord" }
		]
	},
	"prop12": {
		"duration": 1440,
		"instructions": True,
		"live": False,  

		"choices": [
			{ "emoji": "1⃣", "text": "La proposition 1 me satisfait le plus" },
			{ "emoji": "2⃣", "text": "La proposition 2 me satisfait le plus" },
			{ "emoji": "🤷", "text": "Neutre" }
		]
	},
	"prop123": {
		"duration": 1440,
		"instructions": True,
		"live": False,
		"choices": [
			{ "emoji": "1⃣", "text": "La proposition 1 me satisfait le plus" },
			{ "emoji": "2⃣", "text": "La proposition 2 me satisfait le plus" },
			{ "emoji": "3⃣", "text": "La proposition 3 me satisfait le plus" },
			{ "emoji": "🤷", "text": "Neutre" }
		]
	},
	"judge": {
		"duration": 1440,
		"instructions": True,
		"live": False,
		"choices": [
			{ "emoji": "🇷", "text": "À rejeter" },
			{ "emoji": "🇮", "text": "Insuffisant" },
			{ "emoji": "🇵", "text": "Passable" },
			{ "emoji": "🇦", "text": "Assez bien" },
			{ "emoji": "🇧", "text": "Bien" },
			{ "emoji": "🇹", "text": "Très bien" }
		]
	}
}
emojiWithTone = ["👎", "🤷", "👍"]
ongoingVotes = {}
scrutinsToAdd = {}
topics = {}
sharedMessages = {}
sharedMessagesToDelete = []
lastBan = {}

scrutinVoteInfo = "Vous pouvez voter en cliquant sur une « réaction ». Vous recevrez alors une confirmation de vote via message privé. Vous pouvez changer votre vote à tout moment."

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
			dateEnd = self.dateStart + datetime.timedelta(minutes=self.data.get("duration", 0))
			message = message + "**Scrutin ouvert** jusqu'au "+dateEnd.strftime("%d/%m/%y à %H:%M")+"\n"
			
			message = message + scrutinVoteInfo+"\n\n"
		
		if self.question:
			message = message + self.question+"\n"
		
		if self.data.get("instructions", True):
			message = message + "\n"
			for c in self.data.get("choices", []):
				if self.data.get("live", False):
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

class Topic:
	def __init__(self, message):
		self.message = message
		self.counter = 0
		self.dateLast = datetime.datetime.now()
	
	async def sendMessage(self, chan):
		text = ":loudspeaker: "+self.message
		await client.send_message(chan, text)
		
		self.counter = 0
		self.dateLast = datetime.datetime.now()
	
	def check(self):
		if self.counter < 30:
			return False
		
		dateEnd = self.dateLast + datetime.timedelta(minutes=5)
		dateNow = datetime.datetime.now()
		if dateNow < dateEnd:
			return False
		
		return True

class SharedMessage:
	def __init__(self, channelId, messageId):
		self.channelId = channelId
		self.messageId = messageId

try:
	with open('backup.json', 'r') as infile:
		data = json.load(infile)
		
		for topic in data.get("topics", []):
			key = (topic.get("serverId", 0), topic.get("channelId", 0))
			topics[key] = Topic(topic.get("message"))
			topics[key].counter = topic.get("counter", 0)
			topics[key].dateLast = dateutil.parser.parse(topic.get("dateLast", datetime.datetime.isoformat(datetime.datetime.now())))
		
		for sm in data.get("sharedMessages", []):
			key0 = sm.get("serverId", None)
			key1 = sm.get("name", None)
			if key0 and key1:
				sharedMessages[(key0, key1)] = SharedMessage(sm.get("channelId"), sm.get("messageId"))
		
		for scrutin in data.get("scrutins", []):
			key = (scrutin.get("serverId", 0), scrutin.get("channelId", 0), scrutin.get("messageId", 0))
			dateStart = dateutil.parser.parse(scrutin.get("dateStart", datetime.datetime.isoformat(datetime.datetime.now())))
			ongoingVotes[key] = Scrutin(scrutin.get("question"), scrutin.get("data"), scrutin.get("tone"), dateStart)
			ongoingVotes[key].votes = scrutin.get("votes", {})
except:
	print("Can't load backup")
	print(traceback.format_exc())
	pass

"""
0 : Nouveaux-lles
1 : Invité-e-s
2 : Admis-es
3 : Non-mixte
4 : Modération
5 : Technicien-ne-s
6 : Propriétaire
"""
def getMemberLevel(member):
	level = 0
	
	#Seach in NM
	nm = False
	for c in member.server.channels:
		if c.name == "nm_feministe" and c.permissions_for(member).read_messages:
			nm = True
		if c.name == "nm_lgbti" and c.permissions_for(member).read_messages:
			nm = True
		if c.name == "nm_racise-e-s" and c.permissions_for(member).read_messages:
			nm = True
		if c.name == "nm_neuroatypique" and c.permissions_for(member).read_messages:
			nm = True
	
	for r in member.roles:
		if r.name == "Invité-e-s":
			level = max(level, 1)
		if r.name == "Admis-es":
			if nm:
				level = max(level, 3)
			else:
				level = max(level, 2)
		if r.name == "Modération":
			level = max(level, 4)
		if r.name == "Technicien-ne-s":
			level = max(level, 5)
		if r.name == "Propriétaire":
			level = max(level, 6)
	return level

@client.event
async def on_ready():
	print("* Bot "+client.user.name+" logged successfully")
	
	prevTime = time.time()
	while True:
		currTime = time.time()
		sleepDuration = 5 - (currTime - prevTime)
		prevTime = currTime
		if sleepDuration > 0:
			await asyncio.sleep(sleepDuration)
		
		# Backup
		with open('backup.json', 'w') as outfile:
			data = {}
			
			data["topics"] = []
			for t,topic in topics.items():
				data["topics"].append({
					"message": topic.message,
					"counter": topic.counter,
					"dateLast": topic.dateLast.isoformat(),
					"serverId": t[0],
					"channelId": t[1]
				})
			
			data["sharedMessages"] = []
			for sk,sm in sharedMessages.items():
				data["sharedMessages"].append({
					"name": sk[1],
					"serverId": sk[0],
					"channelId": sm.channelId,
					"messageId": sm.messageId,
				})
			
			data["scrutins"] = []
			for s,scrutin in ongoingVotes.items():
				data["scrutins"].append({
					"question": scrutin.question,
					"data": scrutin.data,
					"votes": scrutin.votes,
					"dateStart": scrutin.dateStart.isoformat(),
					"tone": scrutin.tone,
					"serverId": s[0],
					"channelId": s[1],
					"messageId": s[2]
				})
		
			json.dump(data, outfile)
		
		# Topics
		for k,t in topics.items():
			if t.check():
				serv = client.get_server(k[0])
				if not serv:
					break
				chan = serv.get_channel(k[1])
				if not chan:
					break
				
				await t.sendMessage(chan)
		
		# Shared messages
		
		for s in sharedMessagesToDelete:
			del(sharedMessages[s])
		
		
		# Scrutins
		toDelete = set()
		
		for s,scrutin in scrutinsToAdd.items():
			ongoingVotes[s] = scrutin
		
		for s,scrutin in ongoingVotes.items():
			try:
				if ongoingVotes[s].checkTime(datetime.datetime.now() + datetime.timedelta(minutes=1)):
					toDelete.add(s)
				
				serv = client.get_server(s[0])
				if not serv:
					continue
				chan = serv.get_channel(s[1])
				if not chan:
					continue
				
				msg = await client.get_message(chan, s[2])
				
				#check first if there is reaction to take care
				if not ongoingVotes[s].checkTime(datetime.datetime.now() + datetime.timedelta(minutes=1)):
					modification = False
					emojiVisible = []
					for r in msg.reactions:
						try:
							emoji = None
							for c in scrutin.data.get("choices", []):
								if checkEmoji(r, c["emoji"]):
									emoji = c["emoji"]
									break
							
							ra = await client.get_reaction_users(r)
							for a in ra:
								if not emoji:
									await client.remove_reaction(msg, r.emoji, a)
								elif a.id == client.user.id:
									emojiVisible.append(emoji)
								else:
									lastVote = scrutin.getVote(a.id)
									if lastVote == emoji:
										await client.send_message(a, "Vous avez déjà voté "+emoji+" à la question suivante : "+scrutin.question)
									elif lastVote:
										scrutin.setVote(a.id, emoji)
										modification = True
										await client.send_message(a, "Votre vote a été changé de "+lastVote+" vers "+emoji+" pour la question suivante : "+scrutin.question)
									else:
										scrutin.setVote(a.id, emoji)
										modification = True
										await client.send_message(a, "Votre vote a été enregistré. Vous avez voté "+emoji+" à la question suivante : "+scrutin.question)
									
									await client.remove_reaction(msg, r.emoji, a)
							
						except:
							pass
					
					for c in scrutin.data.get("choices", []):
						if c["emoji"] not in emojiVisible:
							await client.add_reaction(msg, c["emoji"])
					
					if modification:
						await client.edit_message(msg, scrutin.getMessage())
				else:
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
			except:
				pass
	
		for k in toDelete:
			del(ongoingVotes[k])
		
@client.event
async def on_message(message):
	try:
		if not message.server:
			return
		
		topicKey = (message.server.id, message.channel.id)
		if topicKey in topics:
			topics[topicKey].counter = topics[topicKey].counter + 1
		
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
			text = text + "``@"+client.user.name+" topic <texte>`` : change le sujet de la discussion.\n"
			text = text + "``@"+client.user.name+" topic`` : supprime le sujet de la discussion.\n"
			text = text + "``@"+client.user.name+" ban @LeNom#1234`` : ban une personne.\n"
			text = text + "``@"+client.user.name+" kick @LeNom#1234`` : kick une personne.\n"
			text = text + "``@"+client.user.name+" add-msg <name> <texte>`` : poste un message éditable par tout le monde. Remplacez <name> par un identifiant pour ce message\n"
			text = text + "``@"+client.user.name+" edit-msg <name> <texte>`` : affiche le code d'un message à partir de son ID ou de son identifiant.\n"
			text = text + "``@"+client.user.name+" view-msg <name ou id>`` : affiche le code d'un message à partir de son ID ou de son identifiant.\n"
			text = text + "``@"+client.user.name+" list-msg`` : affiche la liste des messages éditables.\n"
			text = text + "``@"+client.user.name+" link-msg <name> <channelId> <msgId>`` : ajoute un message posté par ce bot comme message partagé.\n"
			text = text + "``@"+client.user.name+" vote [options] <texte>`` : lancer un scrutin. Remplacez ``<texte>`` par la question à vote.  Les options possibles sont :\n"
			text = text + " - ``short`` : affiche la question du vote et les réactions, mais cache les instructions.\n"
			text = text + " - ``desc`` : affiche uniquement les instructions de vote, sans la question ni les réactions.\n"
			text = text + " - ``h1``, ``h2``, ... : défini la durée du vote à 1 heure, 2 heures, ...\n"
			text = text + " - ``live`` : les résultats sont visibles en directe.\n"
			text = text + " - ``judge`` : le vote sera au jugement majoritaire.\n"
			text = text + " - ``prop12`` : le vote departagera deux propositions.\n"
			text = text + " - ``prop123`` : le vote departagera trois propositions.\n"
			await client.send_message(message.channel, text)
			return
		
		elif cmd == "list-msg":
			msgList = []
			for mId, m in sharedMessages.items():
				if mId[0] == message.server.id:
					msgList.append(mId[1])
			
			await client.send_message(message.channel, "Messages éditables : `"+"`, `".join(msgList)+"`")
		
		elif cmd == "add-msg":
			msgName = msgKeywords[1].strip()
			msgId = (message.server.id, msgName)
			if msgId in sharedMessages:
				await client.send_message(message.channel, "Le nom ``"+msgName+"`` est déjà utilisé.")
				return
			
			msgText = " ".join(msgKeywords[2:])
			
			try:
				msgSent = await client.send_message(message.channel, msgText)
				sharedMessages[msgId] = SharedMessage(message.channel.id, msgSent.id)
				await client.delete_message(message)
				
			except discord.NotFound:
				await client.send_message(message.channel, "Message introuvable.")
				pass
			return
		
		elif cmd == "link-msg":
			msgName = msgKeywords[1].strip()
			msgKey = (message.server.id, msgName)
			chanId = msgKeywords[2].strip()
			msgId = msgKeywords[3].strip()
			
			try:
				if msgId in sharedMessages:
					await client.send_message(message.channel, "Le nom ``"+msgName+"`` est déjà utilisé.")
					return
				
				msgChan = message.server.get_channel(chanId)
				if not msgChan:
					await client.send_message(message.channel, "Message introuvable.")
					return
				
				msgFound = await client.get_message(msgChan, msgId)
				
				sharedMessages[msgKey] = SharedMessage(msgFound.channel.id, msgFound.id)
				await client.delete_message(message)
				
				await client.send_message(message.channel, "Message partagé trouvé : ```\n"+msgFound.content.replace("```", "'''")+"\n```")
			except discord.NotFound:
				await client.send_message(message.channel, "Message introuvable.")
				pass
			return
		
		elif cmd == "edit-msg":
			msgId = (message.server.id, msgKeywords[1].strip())
			msgText = " ".join(msgKeywords[2:])
			
			if msgId not in sharedMessages:
				await client.send_message(message.channel, "Message introuvable.")
				return
					
			msgChanId = sharedMessages[msgId].channelId
			msgChan = message.server.get_channel(msgChanId)
			if not msgChan:
				await client.send_message(message.channel, "Message introuvable.")
				return
			
			msgId = sharedMessages[msgId].messageId
		
			try:
				if not(msgChan.permissions_for(message.author).read_messages and msgChan.permissions_for(message.author).send_messages):
					await client.send_message(message.channel, "Vous n'avez pas les droits pour modifier ce message.")
					return
				
				msgFound = await client.get_message(msgChan, msgId)
				await client.edit_message(msgFound, msgText)
				await client.delete_message(message)
				
			except discord.NotFound:
				await client.send_message(message.channel, "Message introuvable.")
				pass
			return
		
		elif cmd == "delete-msg":
			msgId = (message.server.id, msgKeywords[1].strip())
			msgText = " ".join(msgKeywords[2:])
			
			if msgId not in sharedMessages:
				await client.send_message(message.channel, "Message introuvable.")
				return
					
			msgChanId = sharedMessages[msgId].channelId
			msgChan = message.server.get_channel(msgChanId)
			if not msgChan:
				await client.send_message(message.channel, "Message introuvable.")
				return
			
			msgId = sharedMessages[msgId].messageId
		
			try:
				if not(msgChan.permissions_for(message.author).read_messages and msgChan.permissions_for(message.author).send_messages):
					await client.send_message(message.channel, "Vous n'avez pas les droits pour supprimer ce message.")
					return
				
				msgFound = await client.get_message(msgChan, msgId)
				msgText = msgFound.content
				msgText = msgText.replace("```", "'''")
				await client.delete_message(msgFound)
				await client.send_message(message.channel, "Message supprimé :```\n"+msgText+"\n```")
				sharedMessagesToDelete.append(msgId);
				
			except discord.NotFound:
				await client.send_message(message.channel, "Message introuvable.")
				pass
			return
		
		elif cmd == "view-msg":
			msgId = (message.server.id, msgKeywords[1].strip())
			msgChan = message.channel
			
			try:
				if msgId in sharedMessages:
					msgChanId = sharedMessages[msgId].channelId
					msgChan = message.server.get_channel(msgChanId)
					if not msgChan:
						await client.send_message(message.channel, "Message introuvable.")
						return
					
					msgId = sharedMessages[msgId].messageId
				else:
					msgId = msgKeywords[1].strip()
					
					if not(msgChan.permissions_for(message.author).read_messages):
						await client.send_message(message.channel, "Vous n'avez pas les droits pour afficher ce message.")
						return
				
				msgFound = await client.get_message(msgChan, msgId)
				msgText = msgFound.content
				if msgText.find("```") >= 0:
					await client.send_message(message.channel, "Attention, le message contient des balises codes (```). Pour des raisons d'affichage, elles été remplacées par (''').")
					msgText.replace("```", "'''")
				
				await client.send_message(message.channel, "```\n"+msgText+"\n```")
			except discord.NotFound:
				await client.send_message(message.channel, "Message introuvable.")
				pass
			return
			
		elif cmd == "kick":
			
			dateNow = datetime.datetime.now()
			dateLastBan = dateNow - datetime.timedelta(days=2)
			dateValideBan = dateNow - datetime.timedelta(days=1)
			if lastBan.get(message.author.id, None):
				dateLastBan = lastBan[message.author.id]
			
			if dateLastBan > dateValideBan:
				await client.send_message(message.channel, "Vous avez déjà banni ou kické une personne ces dernières 24h.")
				return
			
			if len(msgKeywords) > 1:
				m = re.search('<@!?([0-9]*)>', msgKeywords[1])
				if m:
					member = message.server.get_member(m.group(1))
					if member:
						levelAuthor = getMemberLevel(message.author)
						levelMember = getMemberLevel(member)
						if levelAuthor < 2:
							await client.send_message(message.channel, "Vous devez être admis-e pour utiliser cette commande.")
						elif member.id == message.author.id:
							await client.send_message(message.channel, "Vous ne pouvez pas vous kicker vous-même.")
						elif levelMember < levelAuthor or (levelMember == 3 and levelAuthor == 3):
							try:
								await client.kick(member)
								lastBan[message.author.id] = dateNow
								await client.send_message(message.channel, message.author.mention+" a kické "+member.display_name+"#"+member.discriminator+" du serveur.")
							except:
								await client.send_message(message.channel, "Impossible de kicker "+member.display_name+".")
								print(traceback.format_exc())
								pass
						else:
							await client.send_message(message.channel, "Vous n'avez pas les droits suffisants pour kicker cette personne.")
					else:
						await client.send_message(message.channel, "Impossible de trouver la personne mentionnée dans ce serveur.")
				else:
					print(msgKeywords[1])
					await client.send_message(message.channel, "Vous devez mentionner une personne à kicker.")
			else:
				print(msgKeywords[1])
				await client.send_message(message.channel, "Vous devez mentionner une personne à kicker.")
			
			return
		
		elif cmd == "ban":
			dateNow = datetime.datetime.now()
			dateLastBan = dateNow - datetime.timedelta(days=2)
			dateValideBan = dateNow - datetime.timedelta(days=1)
			if lastBan.get(message.author.id, None):
				dateLastBan = lastBan[message.author.id]
			
			if dateLastBan > dateValideBan:
				await client.send_message(message.channel, "Vous avez déjà banni ou kické une personne ces dernières 24h.")
				return
			
			if len(msgKeywords) > 1:
				m = re.search('<@!?([0-9]*)>', msgKeywords[1])
				if m:
					member = message.server.get_member(m.group(1))
					if member:
						levelAuthor = getMemberLevel(message.author)
						levelMember = getMemberLevel(member)
						if levelAuthor < 2:
							await client.send_message(message.channel, "Vous devez être admis-e pour utiliser cette commande.")
						elif member.id == message.author.id:
							await client.send_message(message.channel, "Vous ne pouvez pas vous bannir vous-même.")
						elif levelMember < levelAuthor or (levelMember == 3 and levelAuthor == 3):
							try:
								await client.ban(member, 0)
								await client.send_message(message.channel, message.author.mention+" a banni "+member.display_name+"#"+member.discriminator+" du serveur.")
							except:
								await client.send_message(message.channel, "Impossible de bannir "+member.display_name+".")
								pass
						else:
							await client.send_message(message.channel, "Vous n'avez pas les droits suffisants pour bannir cette personne.")
					else:
						await client.send_message(message.channel, "Impossible de trouver la personne mentionnée dans ce serveur.")
				else:
					print(msgKeywords[1])
					await client.send_message(message.channel, "Vous devez mentionner une personne à bannir.")
			else:
				print(msgKeywords[1])
				await client.send_message(message.channel, "Vous devez mentionner une personne à bannir.")
			
			return
		
		elif cmd == "topic":
			topicMsg = " ".join(msgKeywords[1:])
			
			
			if len(topicMsg) == 0:
				if topicKey in topics:
					del(topics[topicKey])
					await client.send_message(message.channel, ":loudspeaker: Sujet de la discussion supprimé.")
			else:
				topics[topicKey] = Topic(topicMsg)
				await client.send_message(message.channel, ":loudspeaker: "+topicMsg)
			
			await client.delete_message(message)
			
			return
		
		elif cmd == "check-activity":
			#~ if getMemberLevel(message.author) < 4:
			if message.author.id != "287858556684730378":
				return
			
			statusMsg = await client.send_message(message.channel, "Analyse en cours...")
			checkDate = message.timestamp - datetime.timedelta(days=30)
			
			userStats = {}
			
			excludedChannels = [
				"shitpost",
				"accueil",
				"chasse_aux_fafs"
			]
			
			for c in message.server.channels:
				if c.type != discord.ChannelType.text:
					continue
				if c.name in excludedChannels:
					continue
				
				msgCounter = 0
				stillNotDone = True
				logLimit = checkDate
				while stillNotDone:
					msgSubCounter = 0
					async for m in client.logs_from(c, limit=100, after=logLimit):
						if msgSubCounter == 0:
							logLimit = m
						msgSubCounter = msgSubCounter+1
						
						prevNum = userStats.get(m.author, 0)
						userStats[m.author] = prevNum+1
						
					msgCounter = msgCounter+msgSubCounter
					if msgSubCounter <= 1:
						stillNotDone = False
				
				await client.edit_message(statusMsg, "Analyse du salon "+c.mention+" : "+str(msgCounter)+ " messages")
			
			text = ""
			for u,numMsg in sorted(userStats.items(), key=operator.itemgetter(1)):
				subText = u.name+" : "+str(numMsg)+" messages\n"
				if len(text) + len(subText) > 1500:
					await client.send_message(message.channel, text)
					text = ""
				text += subText
			await client.send_message(message.channel, text)
			return
		
		elif cmd == "vote":
			skinTone = random.choice(["", "🏻", "🏼", "🏽", "🏾", "🏿"])
			
			chan = message.channel
			
			if not chan:
				return
			
			nextParam = 1
			optLive = False
			optDesc = False
			optShort = False
			duration = 24
			defaultVoteType = "default"
			while nextParam < len(msgKeywords):
				if msgKeywords[nextParam] == "live":
					optLive = True
					nextParam = nextParam+1
				elif msgKeywords[nextParam] == "desc":
					optDesc = True
					nextParam = nextParam+1
				elif msgKeywords[nextParam] == "short":
					optShort = True
					nextParam = nextParam+1
				elif msgKeywords[nextParam] in scrutinType:
					defaultVoteType = msgKeywords[nextParam]
					nextParam = nextParam+1
				else:
					m = re.search('^[hH]([0-9]+)', msgKeywords[nextParam])
					if m:
						duration = int(m.group(1))
						nextParam = nextParam+1
					else:
						break
			
			question = " ".join(msgKeywords[nextParam:])
			
			scrutinData = scrutinType[defaultVoteType]
			scrutinData["duration"] = duration*60
			
			if optDesc:
				txt = ""
				
				dateEnd = datetime.datetime.now() + datetime.timedelta(minutes=scrutinData.get("duration", 0))
				txt = txt + "**Scrutin ouvert** jusqu'au "+dateEnd.strftime("%d/%m/%y à %H:%M")+"\n"
				txt = txt + scrutinVoteInfo+"\n\n"
				
				if question:
					txt = txt + question+"\n"
				
				txt = txt + "\n"
				for c in scrutinData.get("choices", []):
					txt = txt + applyTone(c["emoji"], skinTone)+" : "+c["text"]+"\n\n"
				
				await client.send_message(chan, txt)
				
			else:
				if optShort:
					scrutinData["instructions"] = False
				if optLive:
					scrutinData["live"] = True
				
				scrutin = Scrutin(question, scrutinData, skinTone, datetime.datetime.now())
			
				voteMsg = await client.send_message(chan, scrutin.getMessage())
				voteKey = (voteMsg.server.id, voteMsg.channel.id, voteMsg.id)
				
				scrutinsToAdd[voteKey] = scrutin
			
			await client.delete_message(message)
	except:
		await client.send_message(message.channel, "Oups...")
		print(traceback.format_exc())

client.run(discord_token)
