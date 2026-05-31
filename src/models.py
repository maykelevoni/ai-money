from dataclasses import dataclass
from typing import Optional


@dataclass
class Offer:
    id: int
    network: str
    network_offer_id: str
    name: str
    vertical: str
    payout: float
    geo: str
    status: str  # candidate|testing|winner|loser|excluded
    tracking_url: str
    first_seen: str
    last_tested: Optional[str]


@dataclass
class Campaign:
    id: int
    offer_id: int
    traffic_campaign_id: Optional[str]
    lander_path: str
    status: str  # pending|active|paused|killed
    daily_cap: float
    created_at: str
    notes: Optional[str]


@dataclass
class Creative:
    id: int
    campaign_id: int
    traffic_creative_id: Optional[str]
    title: str
    description: str
    icon_path: Optional[str]
    status: str  # active|paused
    clicks: int
    ctr: float


@dataclass
class Click:
    id: int
    click_id: str
    campaign_id: int
    zone: str
    cost: float
    country: str
    ts: str


@dataclass
class Conversion:
    id: int
    click_id: str
    payout: float
    ts: str


@dataclass
class SpendSnapshot:
    id: int
    campaign_id: int
    zone: str
    spend: float
    clicks: int
    ts: str


@dataclass
class Decision:
    id: int
    ts: str
    scope: str    # zone|creative|campaign|offer
    target_id: str
    action: str   # pause|scale|blacklist|kill|launch
    reason: str
    data_json: Optional[str]


@dataclass
class BudgetLedger:
    id: int
    ts: str
    amount: float
    kind: str  # deposit|spend
    running_total: float
