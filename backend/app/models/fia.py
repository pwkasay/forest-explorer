"""SQLAlchemy ORM models for raw FIA data with PostGIS geometry."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Double, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FIAPlot(Base):
    """Raw FIA plot locations with PostGIS point geometry."""

    __tablename__ = "fia_plot"
    __table_args__ = {"schema": "raw"}

    cn: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    statecd: Mapped[int] = mapped_column(Integer, nullable=False)
    unitcd: Mapped[int | None] = mapped_column(Integer)
    countycd: Mapped[int | None] = mapped_column(Integer)
    plot: Mapped[int | None] = mapped_column(Integer)
    invyr: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float | None] = mapped_column(Double)
    lon: Mapped[float | None] = mapped_column(Double)
    elev: Mapped[int | None] = mapped_column(Integer)
    ecosubcd: Mapped[str | None] = mapped_column(String(10))
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conditions: Mapped[list["FIACond"]] = relationship(back_populates="plot_ref")
    trees: Mapped[list["FIATree"]] = relationship(back_populates="plot_ref")


class FIACond(Base):
    """Raw FIA condition data — stand-level attributes per plot."""

    __tablename__ = "fia_cond"
    __table_args__ = {"schema": "raw"}

    cn: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plt_cn: Mapped[int | None] = mapped_column(BigInteger)
    condid: Mapped[int | None] = mapped_column(Integer)
    statecd: Mapped[int] = mapped_column(Integer, nullable=False)
    fortypcd: Mapped[int | None] = mapped_column(Integer)
    fortypcdname: Mapped[str | None] = mapped_column(String(100))
    stdage: Mapped[int | None] = mapped_column(Integer)
    stdszcd: Mapped[int | None] = mapped_column(Integer)
    siteclcd: Mapped[int | None] = mapped_column(Integer)
    slope: Mapped[int | None] = mapped_column(Integer)
    aspect: Mapped[int | None] = mapped_column(Integer)
    owncd: Mapped[int | None] = mapped_column(Integer)
    owngrpcd: Mapped[int | None] = mapped_column(Integer)
    condprop_unadj: Mapped[float | None] = mapped_column(Double)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    plot_ref: Mapped[FIAPlot | None] = relationship(back_populates="conditions")


class FIATree(Base):
    """Raw FIA tree measurements — individual tree carbon and biomass."""

    __tablename__ = "fia_tree"
    __table_args__ = {"schema": "raw"}

    cn: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plt_cn: Mapped[int | None] = mapped_column(BigInteger)
    condid: Mapped[int | None] = mapped_column(Integer)
    subp: Mapped[int | None] = mapped_column(Integer)
    tree: Mapped[int | None] = mapped_column(Integer)
    statecd: Mapped[int] = mapped_column(Integer, nullable=False)
    spcd: Mapped[int] = mapped_column(Integer, nullable=False)
    dia: Mapped[float | None] = mapped_column(Double)
    ht: Mapped[float | None] = mapped_column(Double)
    actualht: Mapped[float | None] = mapped_column(Double)
    cr: Mapped[int | None] = mapped_column(Integer)
    statuscd: Mapped[int | None] = mapped_column(Integer)
    drybio_ag: Mapped[float | None] = mapped_column(Double)
    drybio_bg: Mapped[float | None] = mapped_column(Double)
    carbon_ag: Mapped[float | None] = mapped_column(Double)
    carbon_bg: Mapped[float | None] = mapped_column(Double)
    tpa_unadj: Mapped[float | None] = mapped_column(Double)
    volcfnet: Mapped[float | None] = mapped_column(Double)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    plot_ref: Mapped[FIAPlot | None] = relationship(back_populates="trees")
