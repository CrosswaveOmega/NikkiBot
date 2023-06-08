from sqlalchemy import Column, ForeignKey, Integer, String, Double
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from database import DatabaseSingleton
MusicBase = declarative_base(name="Music System Base")


class UserMusicProfile(MusicBase):
    __tablename__ = 'user_music_profiles'

    user_id = Column(Integer, primary_key=True)
    total_upload_number = Column(Integer, default=0)
    playlist_number = Column(Integer, default=0)
    upload_limit = Column(Integer,default=4)

    uploads = relationship("UserUploads", back_populates="user_profile")
    @classmethod
    def get(cls, user_id):
        session:Session = DatabaseSingleton.get_session()
        result = session.query(UserMusicProfile).filter_by(user_id=user_id).first()
        if result:            return result
        else:            return None
    
    @staticmethod
    def get_or_new(user_id):
        new=UserMusicProfile.get(user_id)
        if not new:
            session=DatabaseSingleton.get_session()
            new = UserMusicProfile(user_id=user_id)
            session.add(new)
            session.commit()
        return new
    
    def add_song(self, file_path: str, file_size: int):
        session:Session = DatabaseSingleton.get_session()
        new_upload_number = self.total_upload_number + 1
        new_upload = UserUploads(
            user_id=self.user_id,
            upload_number=new_upload_number,
            file_path=file_path,
            file_size=file_size
        )
        session.add(new_upload)
        self.uploads.append(new_upload)
        self.total_upload_number = new_upload_number
        session.commit()

    def check_upload_limit(self):
        return self.total_upload_number >= self.upload_limit

    def remove_song(self, upload_number: int):
        session:Session = DatabaseSingleton.get_session()
        upload = session.query(UserUploads).filter_by(user_id=self.user_id, upload_number=upload_number).first()
        if upload:
            session.delete(upload)
            self.uploads.remove(upload)
            self.total_upload_number -= 1
            session.commit()
    def check_existing_upload(self, file_path: str):
        session:Session = DatabaseSingleton.get_session()
        existing_upload = session.query(UserUploads).filter_by(file_path=file_path).first()
        return existing_upload is not None



class UserUploads(MusicBase):
    __tablename__ = 'user_uploads'

    user_id = Column(Integer, ForeignKey('user_music_profiles.user_id'), primary_key=True)
    upload_number = Column(Integer, primary_key=True)
    file_path = Column(String)
    file_size = Column(Double)

    user_profile = relationship("UserMusicProfile", back_populates="uploads")

DatabaseSingleton('mainsetup').load_base(MusicBase)