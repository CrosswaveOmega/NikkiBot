from typing import List, Tuple
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, and_, or_
from sqlalchemy.orm import relationship, joinedload
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import discord
from database import DatabaseSingleton, AwareDateTime
from utility import hash


PollingBase = declarative_base(name="Polling System Base")

class PollTable(PollingBase):
    __tablename__ = 'poll_table'
    poll_id = Column(Integer, primary_key=True)
    poll_hex = Column(String,nullable=False,unique=True)
    poll_name = Column(String)
    poll_text = Column(String)
    choices = Column(Integer, default=2)
    choice_a = Column(String)
    choice_b = Column(String)
    choice_c = Column(String, nullable=True)
    choice_d = Column(String, nullable=True)
    choice_e = Column(String, nullable=True)
    start_date = Column(AwareDateTime, default=datetime.now())
    end_date = Column(AwareDateTime, nullable=True)
    active= Column(Boolean, default=True)
    result_a = Column(Integer, default=0)
    result_b = Column(Integer, default=0)
    result_c = Column(Integer, default=0, nullable=True)
    result_d = Column(Integer, default=0, nullable=True)
    result_e = Column(Integer, default=0, nullable=True)
    made_by = Column(Integer)
    scope = Column(String)
    change_vote = Column(Boolean, default=False)
    server_id = Column(Integer, nullable=True)
    
    @staticmethod
    def new_poll(poll_name, poll_text, choices, choice_a, choice_b, choice_c=None, choice_d=None, choice_e=None, start_date=None, end_date=None, made_by=None, scope="Global", change_vote=True, server_id=None):
        session = DatabaseSingleton.get_session()
        poll = PollTable(poll_name=poll_name, poll_text=poll_text, choices=choices, 
                         choice_a=choice_a, 
                         choice_b=choice_b, 
                         choice_c=choice_c, 
                         choice_d=choice_d, 
                         choice_e=choice_e, 
                         start_date=start_date, end_date=end_date, 
                         made_by=made_by, scope=scope, change_vote=False, server_id=server_id)
        name,x=hash.hash_string(str(poll.poll_id),7,hash.Hashsets.hex)
        poll.poll_hex=name
        session.add(poll)
        session.commit()
        return poll

    @classmethod
    def get(cls, poll_id):
        session= DatabaseSingleton.get_session()
        result = session.query(PollTable).filter_by(poll_id=poll_id).first()
        if result:
            if result.poll_hex==None:
                name,x=hash.hash_string(str(result.poll_id),7,hash.Hashsets.hex)
                result.poll_hex=name
                session.commit()
            return result
        else:            return None
    
    @classmethod
    def get_by_hex(cls, poll_id):
        session= DatabaseSingleton.get_session()
        result = session.query(PollTable).filter_by(poll_hex=poll_id).first()
        if result:
            if result.poll_hex==None:
                name,x=hash.hash_string(str(result.poll_id),7,hash.Hashsets.hex)
                result.poll_hex=name
                session.commit()
            return result
        else:            return None

    def poll_buttons(poll):
        buttons = []
        for i in range(1, poll.choices + 1):
            button_id = f"{poll.poll_id}:choice_{chr(ord('a')+i-1)}"
            choice_text = getattr(poll, f"choice_{chr(ord('a')+i-1)}")
            buttons.append((button_id, choice_text))
        return buttons

    @staticmethod
    def vote(button_id, user_id):
        session = DatabaseSingleton.get_session()
        poll_id, choice = button_id.split(':')
        poll = session.query(PollTable).filter_by(poll_id=poll_id).first()
        if datetime.now() > poll.end_date:
            return "This poll is over." 
        poll_data = session.query(PollData).filter(and_(PollData.poll_id==poll_id, PollData.user_id==user_id)).first()
        mypoll=PollTable.get(poll_id)
        
        if poll_data:
            #return "You have already voted and cannot change your vote.", mypoll
            new_choice=choice.split('_')[1].upper()
            if poll_data.choice!=new_choice:
                poll.change_vote=True
                poll_data.choice = new_choice
                session.commit()
        else:
            poll.change_vote=True
            poll_data = PollData(poll_id=poll_id, user_id=user_id, choice=choice.split('_')[1].upper())
            session.add(poll_data)
            
            session.commit()
        
        mypoll.tally()
        
        return "Your vote has been recorded.", mypoll

    def tally(poll):
        active = poll.active
        session = DatabaseSingleton.get_session()
        poll_data = session.query(PollData).filter_by(poll_id=poll.poll_id).all()
        total_votes = len(poll_data)
        votes_a = votes_b = votes_c = votes_d = votes_e = 0
        for data in poll_data:
            choice = data.choice
            if choice == 'A':
                votes_a += 1
            elif choice == 'B':
                votes_b += 1
            elif choice == 'C':
                votes_c += 1
            elif choice == 'D':
                votes_d += 1
            elif choice == 'E':
                votes_e += 1
        poll.result_a = votes_a
        poll.result_b = votes_b
        poll.result_c = votes_c
        poll.result_d = votes_d
        poll.result_e = votes_e
        session.commit()

    def get_tally(poll):
        active = poll.active
        session = DatabaseSingleton.get_session()
        total_votes = (poll.result_a+ poll.result_b+ poll.result_c+poll.result_d+poll.result_e)
        return total_votes, poll.result_a,  poll.result_b,  poll.result_c, poll.result_d, poll.result_e

    @staticmethod
    def is_real(poll_id):
        session = DatabaseSingleton.get_session()
        poll = session.query(PollTable).get(poll_id)
        if poll:
            return True
        return False
        

    def is_active(poll):
        current_time = datetime.now()
        if (poll.end_date>current_time):
            return True
        return False

    @staticmethod
    def update_poll_status():
        session = DatabaseSingleton.get_session()
        current_time = datetime.now()
        polls_to_update = session.query(PollTable).filter(PollTable.end_date <= current_time, PollTable.active == True).all()
        for poll in polls_to_update:
            poll.active = False
        session.commit()
    @staticmethod
    def get_active_polls(server_id):
        session = DatabaseSingleton.get_session()
        active_polls = []
        current_time = datetime.now()
        for poll in session.query(PollTable).filter(
            PollTable.end_date > current_time,
            ((PollTable.scope == 'global') | ((PollTable.scope == 'server') & (PollTable.server_id == server_id)))
        ):
            active_polls.append(poll)
        return active_polls

    
    
    def poll_embed_view(poll):
        if poll is None:
            return None
        poll_name = poll.poll_name
        poll_text = poll.poll_text
        active = poll.active
        embs=['<:resp_A:1107355323758546977>','<:resp_B:1107355324979093545>','<:resp_C:1107355327302746152>','<:resp_D:1107355331836788798>','<:resp_E:1107355337171927090>']
        tally = poll.get_tally()
        total_votes, votes_a, votes_b, votes_c, votes_d, votes_e=tally
        poll_end_time = poll.end_date
        time_str =  f"<t:{int(poll_end_time.timestamp())}:R>"
        if active:
            time_str=f"Until: {time_str}"
        else:
            time_str=f"Poll Closed: <t:{int(poll_end_time.timestamp())}:f>"
        embed = discord.Embed(title=f"<:voteicon:1106567262086901821>{poll_name}", description=f"{poll_text}\n{time_str}")
        #embed.add_field(name=f"Time",value=f"{time_str}")
        for i, (button_id, choice_text) in enumerate(poll.poll_buttons()):
            t=tally[i+1]
            embed.add_field(name=f"{embs[i]}:{choice_text}", value=f"{t} Votes", inline=True)
        embed.set_footer(text=f"Total Votes: {total_votes} ")
        return embed

    @staticmethod
    def poll_list(poll_ids):
        session = DatabaseSingleton.get_session()
        polls = []
        for pi in poll_ids:
            poll_id,pollname=pi
            poll = session.query(PollTable).get(poll_id)
            
            if poll is not None:
                if poll.poll_hex==None:
                    name,x=hash.hash_string(str(poll.poll_id),7,hash.Hashsets.hex)
                    poll.poll_hex=name
                session.commit()
                polls.append(poll)
        embeds = []
        for i in range(0, len(polls), 5):
            embed = discord.Embed(title="Active Poll List",
            description="Below is a list of currently active polls.  To grab one of them to vote, use the `/link_poll` command with the poll id. "
            )
            for poll in polls[i:i+5]:
                name = f"{poll.poll_name}, id:(`{poll.poll_id}`), hex:(`{poll.poll_hex}`)"
                value = f"{poll.poll_text}\n\n"
                embed.add_field(name=name, value=value, inline=False)
            embeds.append(embed)
        return embeds

    @staticmethod
    def get_inactive_polls():
        session = DatabaseSingleton.get_session()
        inactive_polls = session.query(PollTable).filter_by(active=False).all()
        return inactive_polls

class PollData(PollingBase):
    __tablename__ = 'poll_data'
    poll_id = Column(Integer, ForeignKey('poll_table.poll_id'), primary_key=True)
    user_id = Column(Integer, primary_key=True)
    choice = Column(String)
    poll = relationship("PollTable", backref="poll_data")


class PollMessages(PollingBase):
    __tablename__ = 'poll_messages'
    poll_id = Column(Integer, ForeignKey('poll_table.poll_id'), primary_key=True)
    message_id = Column(Integer, primary_key=True)
    message_url = Column(String, default="")
    poll = relationship("PollTable", backref="poll_messages")

    @staticmethod
    def add_poll_message(poll_id: int, message:discord.Message) -> "PollMessages":
        session = DatabaseSingleton.get_session()
        id,url=message.id,message.jump_url
        poll_message = PollMessages(poll_id=poll_id, message_id=id, message_url=url)
        session.add(poll_message)
        session.commit()
        session.refresh(poll_message)
        return poll_message
    @staticmethod
    def get_active_poll_messages() -> List[Tuple[PollTable, List[Tuple[int, str]]]]:
        session = DatabaseSingleton.get_session()
        poll_tables = session.query(PollTable).filter(PollTable.active == True).options(joinedload(PollTable.poll_messages)).all()
        result = []
        for poll_table in poll_tables:
            messages = [(poll_message.message_id, poll_message.message_url) for poll_message in poll_table.poll_messages]
            result.append((poll_table, messages))
        return result
    
    @staticmethod
    def get_inactive_poll_messages() -> List[Tuple[PollTable, List[Tuple[int, str]]]]:
        session = DatabaseSingleton.get_session()
        poll_tables = session.query(PollTable).filter(PollTable.active == False).options(joinedload(PollTable.poll_messages)).all()
        result = []
        for poll_table in poll_tables:
            messages = [(poll_message.message_id, poll_message.message_url) for poll_message in poll_table.poll_messages]
            result.append((poll_table, messages))
        return result

    @staticmethod
    def remove_invalid_poll_messages() -> int:
        session = DatabaseSingleton.get_session()
        invalid_poll_messages = session.query(PollMessages).join(PollTable).filter(PollTable.active == False).all()
        count = 0
        for poll_message in invalid_poll_messages:
            session.delete(poll_message)
            count += 1
        session.commit()
        return count

    @staticmethod
    def remove_poll_message(message_id: int) -> int:
        session = DatabaseSingleton.get_session()
        poll_message = session.query(PollMessages).filter_by(message_id=message_id).first()
        if poll_message:
            session.delete(poll_message)
            session.commit()
            return True
        else:
            return False


class PollChannelSubscribe(PollingBase):
    __tablename__ = 'poll_channel_sub'
    channel_id = Column(Integer, nullable=False)
    server_id = Column(Integer, primary_key=True)
    latest_datetime = Column(AwareDateTime, default=datetime.fromtimestamp(5092))
    polls_retrieved= Column(Integer, default=0)

    @staticmethod
    def set_or_update(channel_id, server_id):
        session = DatabaseSingleton.get_session()
        entry = session.query(PollChannelSubscribe).filter_by(server_id=server_id).first()
        if entry:
            entry.channel_id = channel_id
        else:
            entry = PollChannelSubscribe(channel_id=channel_id, server_id=server_id)
            session.add(entry)
        session.commit()
    @classmethod
    def get(cls, server_id):
        """
        Returns the entire ServerArchiveProfile entry for the specified server_id, or None if it doesn't exist.
        """
        session = DatabaseSingleton.get_session()
        result = session.query(PollChannelSubscribe).filter_by(server_id=server_id).first()
        if result:            return result
        else:            return None
    def __str__(self):
        stri=f"{self.channel_id},{self.server_id},{self.latest_datetime},{self.polls_retrieved}"
    @staticmethod
    def get_new_polls():
        session = DatabaseSingleton.get_session()
        subs = session.query(PollChannelSubscribe).all()
        poll_list = []
        for sub in subs:
            poll_ids = session.query(PollTable).filter(
                PollTable.start_date > sub.latest_datetime,
                PollTable.active == True,  # Only retrieve active polls
                or_(
                    PollTable.scope == 'global',
                    and_(
                        PollTable.scope == 'server',
                        PollTable.server_id == sub.server_id
                    )
                )
            ).all()
            poll_list.append((sub.channel_id, poll_ids))
            sub.latest_datetime = datetime.now()
            sub.polls_retrieved += len(poll_ids)
        session.commit()
        return poll_list



DatabaseSingleton('setup').load_base(PollingBase)
