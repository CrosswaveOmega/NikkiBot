import json
from typing import List, Tuple
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Double,
    JSON,
    and_,
    or_,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, Session
from database import DatabaseSingleton
from sqlalchemy import case, func
from .MusicUtils import is_url
from urllib.parse import parse_qs, urlsplit
import gui

MusicBase = declarative_base(name="Music System Base")


class MusicJSONMemoryDB(MusicBase):
    __tablename__ = "music_json_memory_db"
    url = Column(String, primary_key=True, unique=True, nullable=False)
    title = Column(String, default="titleunknown")
    id = Column(String, default="NOID")
    source = Column(String, default="unknown")
    infojson = Column(JSON, default={})

    def __init__(self, url: str, title: str, id: str, source: str, infojson: dict):
        self.url = url
        self.title = title
        self.id = id
        self.source = source
        self.infojson = infojson

    @staticmethod
    def from_dict(infojson: dict):
        url = infojson["webpage_url"]
        id = infojson["id"]
        title = infojson["title"]
        source = infojson.get("extractor", "???")
        MusicJSONMemoryDB.add_or_update(url, title, id, source, infojson)

    @staticmethod
    def add_or_update(url, title, id, source, infojson):
        session: Session = DatabaseSingleton.get_new_session()
        profile = session.query(MusicJSONMemoryDB).filter_by(url=url).first()
        if not profile:
            profile = MusicJSONMemoryDB(
                url=url, title=title, id=id, source=source, infojson=infojson
            )
            session.add(profile)
            gui.gprint(json.dumps(infojson, indent=3, sort_keys=True))
        else:
            profile.update(url=url, title=title, id=id, infojson=infojson)
        session.commit()
        session.close()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f"{self.url}: {self.title}, {self.id}"

    @classmethod
    def get_part_conditionals(cls, sub_count: List[Tuple[str, int]]):
        """return conditionals."""
        part_conditions = [
            or_(
                cls.id.ilike(f"%{part}%"),
                cls.title.ilike(f"%{part}%"),
                cls.url.ilike(f"%{part}%"),
            )
            for part, count in sub_count
            if count > 0
        ]
        return part_conditions

    @classmethod
    def count_total_substring_matches(
        cls, parts: List[str], session=None
    ) -> List[Tuple[str, int]]:
        """
        Count the total number of distinct substring matches in the database table for a given list of substrings.

        Parameters:
        -----------
        parts (List[str]):
            A list of substrings to search the database for.

        Returns:
        --------
        List[Tuple[str, int]]:
            A list of tuples where each tuple contains a part and the corresponding count of matches found.

        Notes:
        ------
        - This method performs a case-insensitive substring match on the 'id', 'title', and 'url' columns of the database table.
        - The count includes all matches where the given part is found within any of the three columns.

        """
        if not session:
            session: Session = DatabaseSingleton.get_session()

        # List of conditions for each part
        part_conditions = [
            or_(
                cls.id.ilike(f"%{part}%"),
                cls.title.ilike(f"%{part}%"),
                cls.url.ilike(f"%{part}%"),
            )
            for part in parts
            if part and not part.isspace()
        ]
        # Construct a list of case statements to count matches for each part
        case_statements = [
            func.sum(case((condition, 1), else_=0)).label(f"{part}_count")
            for part, condition in zip(parts, part_conditions)
        ]

        part_counts_query = session.query(*case_statements).first()

        # Extract the results as (part, count) tuples
        part_matches = [
            (part, count) for part, count in zip(parts, part_counts_query) if count > 0
        ]

        return part_matches

    @classmethod
    def max_search(cls, sub_count: List[Tuple[str, int]], session=None) -> List:
        """
        Search for and sort entries by the number of substrings in parts that they contain.

        Parameters:
        - sub_count (List[Tuple[str,int]]): List of substrings with their total occurance count.

        Returns:
        - List[Tuple[MusicJSONMemoryDB, int]]: A list of tuples containing the matching entries
            and their respective total count of substring matches.
        """
        if not session:
            session: Session = DatabaseSingleton.get_session()

        # List of conditions for each part
        part_conditions = cls.get_part_conditionals(sub_count)

        # Construct the case statements to count matches for each part individually
        case_statements = []
        for pc, condition in zip(sub_count, part_conditions):
            part, count = pc
            if count > 0:
                case_statement = case((condition, 1)).label(f"{part}_count")
                case_statements.append(case_statement)

        # Calculate the sum of counts for each ID
        sum_of_counts = sum(
            func.coalesce(case_statement, 0) for case_statement in case_statements
        )

        # Query to get the final results and sort by the sum
        query = (
            session.query(cls, sum_of_counts.label("total_count"))
            .group_by(cls)
            .order_by(sum_of_counts.desc())
            .limit(10)
        )

        # Execute the query and fetch all results
        results = query.all()

        maxdistinct_matches = [
            (result[0], result[1]) for result in results if result[1] > 0
        ]

        return maxdistinct_matches

    @classmethod
    def max_search_tup(cls, parts):
        """same as max search, but returns a tuple."""
        session: Session = DatabaseSingleton.get_session()

        # List of conditions for each part
        part_conditions = [
            or_(
                cls.id.ilike(f"%{part}%"),
                cls.title.ilike(f"%{part}%"),
                cls.url.ilike(f"%{part}%"),
            )
            for part in parts
            if part and not part.isspace()
        ]

        # Construct a list of case statements to count matches for each part
        case_statements = [
            func.count(case((condition, 1))).label(f"{part}_count")
            for part, condition in zip(parts, part_conditions)
        ]

        # Query to get the counts of matches for each part and group by the primary key (id)
        query = (
            session.query(cls.url, *case_statements)
            .group_by(cls.url)
            .order_by(func.count().desc())
            .limit(10)
        )

        # Execute the query and fetch all results
        results = query.all()

        # Extract the results as (id, count) tuples
        maxdistinct_matches = [(result[0], result[1:]) for result in results]

        return maxdistinct_matches

    @classmethod
    def and_search(
        cls, parts: List[str], sub_count: List[Tuple[str, int]], session=None
    ) -> List:
        """
        Search for entries that contain all substrings somewhere in its fields.

        Parameters:
        -----------
        parts : List[str]
            A list of strings representing the substrings to search for in the fields.

        sub_count : List[Tuple[str, int]]
            A list of tuples containing the substrings and their respective counts.

        Returns:
        --------
        List[MusicJSONMemoryDB]
            A list of matched elements that contain all of the provided substrings in their fields.

        Notes:
        ------
        - This method performs a case-insensitive substring match on the 'id', 'title', and 'url' fields of the entries.
        - It searches for entries that contain all of the substrings provided in the 'parts' list.
        - The 'sub_count' list is used to filter the substrings based on their counts.
        - The matched elements are limited to 15 records.


        """
        if not session:
            session: Session = DatabaseSingleton.get_session()
        conditions = and_(
            *[
                cls.id.ilike(f"%{part}%")
                | cls.title.ilike(f"%{part}%")
                | cls.url.ilike(f"%{part}%")
                for part, count in sub_count
                if count > 0
            ]
        )
        conditions = and_(*cls.get_part_conditionals(sub_count))

        matched_elements = session.query(cls).filter(conditions).limit(15).all()
        gui.dprint("outcome", matched_elements)
        if not matched_elements:
            return []
        return matched_elements
        # Find the count of matches for each result element.

    @classmethod
    def substring_search(
        cls, parts: List[str], do_maxsearch: bool = False, session=None
    ) -> List:
        """
        Search the database for entries that can contain all or most of the substrings in `parts`.
        Will utilize an "And" search a
        Parameters:
        -----------
        parts : List[str]
            A list of the substrings to search for in the table's entries.

        do_maxsearch : bool, optional
            A boolean flag indicating whether to perform a max search if no exact match is found
            (default is False).

        Returns:
        --------
        List
            A list of matched entries that contain all or most of the substrings.

        Notes:
        ------
        - This method performs a substring search on the database table based on the provided substrings.
        - It first performs an "and" search to find entries that contain all of the substrings.
        - If no exact match is found, and the `do_maxsearch` flag is True, it performs a max search.
        - The max search finds entries that contain at least one substring,
           ordering them by the total number of matched substrings.
        - The returned list includes either the results from the 'and search' or the 'max search.'

        """
        if not parts or all(part.isspace() for part in parts):
            return []
        # Count how many times each substring was found in any entry
        # in this table.
        subcount = cls.count_total_substring_matches(parts, session=session)
        # And Search checks for entries that contain all of the substrings in parts.
        # If there are none, move on to max_search.
        andsearch = cls.and_search(parts, subcount, session=session)
        if andsearch:
            gui.dprint("found result with and search.")
            return andsearch
        if do_maxsearch:
            # Max Search searches for all entries that contain at least one substring,
            # Ordering by the total number of matched substrings.
            p3 = cls.max_search(subcount, session=session)
            gui.dprint("found resutl with max search")
            return [i for i, s in p3 if s > 0]
        return []

    @classmethod
    def search(cls, query: str, do_sub: bool = True, do_maxsearch: bool = False):
        """
        Search for entries in the database that match the given query.

        Parameters:
        - query (str): The search query string.
        - do_sub (bool, optional): Whether to perform partial substring matching. Defaults to True.

        Returns:
        - List[MusicJSONMemoryDB]: A list of MusicJSONMemoryDB objects that match the search query.
        """
        session: Session = DatabaseSingleton.get_new_session()
        results = (
            session.query(cls)
            .filter(
                (cls.id.ilike(f"%{query}%"))
                | (cls.title.ilike(f"%{query}%"))
                | (cls.url.ilike(f"%{query}%"))
            )
            .limit(10)
            .all()
        )
        if results:
            session.close()
            return results
        if do_sub:
            parts = []
            # Time to check for partial matches.
            if is_url(query):
                gui.gprint("searching urls")
                # Include the whole query as one part initially
                parts = [query]
                # Split the query by the URL components: domain, basename, and GET parameters
                url_components = urlsplit(query)
                gui.dprint(url_components)
                if (
                    url_components.scheme and url_components.netloc
                ):  # Ensure it's a valid URL
                    domain = url_components.netloc
                    basename = url_components.path.lstrip("/")
                    get_params = url_components.query
                    parts.extend([domain, basename, get_params])
                    # Split GET parameters and add them as separate parts
                    params_dict = parse_qs(get_params)
                    for param_key, param_values in params_dict.items():
                        parts.append(param_key)
                        for param_value in param_values:
                            parts.append(param_value)
            else:
                parts = query.split()
            res = MusicJSONMemoryDB.substring_search(
                parts, do_maxsearch=do_maxsearch, session=session
            )
            session.close()
            return res
        else:
            session.close()
            return []


class UserMusicProfile(MusicBase):
    __tablename__ = "user_music_profiles"

    user_id = Column(Integer, primary_key=True)
    total_upload_number = Column(Integer, default=0)
    playlist_number = Column(Integer, default=0)
    upload_limit = Column(Integer, default=4)

    uploads = relationship("UserUploads", back_populates="user_profile")

    likes = relationship("UserLikes", back_populates="user_profile")

    @classmethod
    def get(cls, user_id):
        session: Session = DatabaseSingleton.get_session()
        result = session.query(UserMusicProfile).filter_by(user_id=user_id).first()
        if result:
            return result
        else:
            return None

    @staticmethod
    def get_or_new(user_id):
        new = UserMusicProfile.get(user_id)
        if not new:
            session = DatabaseSingleton.get_session()
            new = UserMusicProfile(user_id=user_id)
            session.add(new)
            session.commit()
        return new

    def add_song(self, file_path: str, file_size: int):
        session: Session = DatabaseSingleton.get_session()
        new_upload_number = self.total_upload_number + 1
        new_upload = UserUploads(
            user_id=self.user_id,
            upload_number=new_upload_number,
            file_path=file_path,
            file_size=file_size,
        )
        session.add(new_upload)
        self.uploads.append(new_upload)
        self.total_upload_number = new_upload_number
        session.commit()

    def check_upload_limit(self):
        return self.total_upload_number >= self.upload_limit

    def remove_song(self, upload_number: int):
        session: Session = DatabaseSingleton.get_session()
        upload = (
            session.query(UserUploads)
            .filter_by(user_id=self.user_id, upload_number=upload_number)
            .first()
        )
        if upload:
            session.delete(upload)
            self.uploads.remove(upload)
            self.total_upload_number -= 1
            session.commit()

    def check_existing_upload(self, file_path: str):
        session: Session = DatabaseSingleton.get_session()
        existing_upload = (
            session.query(UserUploads).filter_by(file_path=file_path).first()
        )
        return existing_upload is not None


class UserLikes(MusicBase):
    __tablename__ = "user_likes"

    user_id = Column(
        Integer, ForeignKey("user_music_profiles.user_id"), primary_key=True
    )
    upload_number = Column(Integer, primary_key=True)
    file_path = Column(String)
    file_size = Column(Double)

    user_profile = relationship("UserMusicProfile", back_populates="likes")


class UserUploads(MusicBase):
    __tablename__ = "user_uploads"

    user_id = Column(
        Integer, ForeignKey("user_music_profiles.user_id"), primary_key=True
    )
    upload_number = Column(Integer, primary_key=True)
    file_path = Column(String)
    file_size = Column(Double)

    user_profile = relationship("UserMusicProfile", back_populates="uploads")


DatabaseSingleton("mainsetup").load_base(MusicBase)
