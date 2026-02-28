const API_URL = "http://127.0.0.1:8000";

export const apiService = {
    async placeTrade(type, userId, symbol, quantity) {
        const response = await fetch(`${API_URL}/${type}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                symbol: symbol.toUpperCase(),
                quantity: parseInt(quantity)
            }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Trade failed");
        return data;
    },

    async createFD(userId, amount, duration) {
        const response = await fetch(`${API_URL}/create_fd`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                amount: parseFloat(amount),
                duration_months: parseInt(duration)
            }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "FD creation failed");
        return data;
    }
};