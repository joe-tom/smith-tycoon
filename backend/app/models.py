from pydantic import BaseModel


class MaterialIn(BaseModel):
    material_id: int
    qty: int


class ForgeRequest(BaseModel):
    materials: list[MaterialIn]
    weapon_type: str  # 한손검, 양손검, ...


class WeaponOut(BaseModel):
    id: int
    name: str
    type: str
    rarity: int
    sharpness: int
    attribute: str | None
    skill: str
    str_req: int
    mag_req: int


class NegotiateRequest(BaseModel):
    weapon_id: int
    price_offered: int
    player_message: str
    negotiation_id: int | None = None
    idempotency_key: str | None = None


class NegotiateResponse(BaseModel):
    negotiation_id: int
    decision: str  # accept / reject / counter
    counter_price: int | None
    message: str


class FinalizeRequest(BaseModel):
    negotiation_id: int


class BattleResponse(BaseModel):
    script: str
    outcomes: dict
    next_phase: str


class MerchantNegotiateRequest(BaseModel):
    merchant_id: int
    price_offered: int
    player_message: str
    negotiation_id: int | None = None


class MerchantSkipRequest(BaseModel):
    merchant_id: int
