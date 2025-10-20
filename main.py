# Основной вебхук — принимает сигнал с TradingView
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("=== RECEIVED WEBHOOK ===")   # 👈 Добавлено
        print(data)                        # 👈 Добавлено
    except:
        raise HTTPException(400, "Invalid JSON")

    direction  = data.get("direction", "NONE")
    symbol     = data.get("symbol", "UNKNOWN")
    confidence = float(data.get("confidence", 0))
    expiry     = int(data.get("expiry_minutes", 5))

    # Если сигнал слабый — пропускаем
    if direction == "NONE" or confidence < 0.97:
        await send_tg("следующая", buttons=False)
        return {"ok": True, "skipped": True}

    # Сохраняем сигнал
    global LAST_SIGNAL
    LAST_SIGNAL = {
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "expiry": expiry,
        "stake": BASE_STAKE,
        "ts": time.time(),
        "approved_at": None,
        "skipped_at": None,
    }

    # Отправляем сигнал в Telegram
    text = f"{direction} 5M ({int(confidence*100)}%) — {symbol}\nВход через: {ENTRY_DELAY} сек\nСтавка: {BASE_STAKE} ₸"
    await send_tg(text, buttons=True)
    return {"ok": True, "sent": True}
