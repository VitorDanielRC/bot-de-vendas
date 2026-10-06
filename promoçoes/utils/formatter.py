from models import Offer


def brl(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def format_offer_message(offer: Offer) -> str:
    lines = [
        "🔥 OFERTA ENCONTRADA 🔥",
        "",
        f"🛒 {offer.title}",
        "",
        f"🏪 {offer.store}",
        "",
    ]
    if offer.original_price and offer.original_price > offer.price:
        lines.append(f"❌ De: {brl(offer.original_price)}")
    lines.append(f"✅ Por: {brl(offer.price)}")
    if offer.discount is not None:
        lines.extend(["", f"💥 {offer.discount:.0f}% OFF"])
    if offer.coupon:
        lines.extend(["", "🎟️ CUPOM:", offer.coupon])
    lines.extend(["", "🔗 COMPRAR:", offer.url, "", "⚡ Oferta sujeita a alteração ou encerramento."])
    return "\n".join(lines)

