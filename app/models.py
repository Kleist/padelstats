"""Database schema. Change via a new Alembic migration in migrations/versions/."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    played_on: Mapped[date] = mapped_column(Date, index=True)
    venue: Mapped[str] = mapped_column(String(20))  # "Inde" or "Ude"
    a1_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    a2_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    b1_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    b2_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    a1: Mapped[Player] = relationship(foreign_keys=[a1_id], lazy="joined")
    a2: Mapped[Player] = relationship(foreign_keys=[a2_id], lazy="joined")
    b1: Mapped[Player] = relationship(foreign_keys=[b1_id], lazy="joined")
    b2: Mapped[Player] = relationship(foreign_keys=[b2_id], lazy="joined")
    sets: Mapped[list["MatchSet"]] = relationship(
        back_populates="match", order_by="MatchSet.set_no", cascade="all, delete-orphan", lazy="selectin"
    )


class MatchSet(Base):
    __tablename__ = "match_sets"
    __table_args__ = (
        CheckConstraint("games_a >= 0 AND games_a <= 7", name="games_a_range"),
        CheckConstraint("games_b >= 0 AND games_b <= 7", name="games_b_range"),
    )

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)
    set_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    games_a: Mapped[int] = mapped_column(Integer)
    games_b: Mapped[int] = mapped_column(Integer)

    match: Mapped[Match] = relationship(back_populates="sets")
