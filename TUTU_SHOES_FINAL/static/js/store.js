function getCart() {
    try {
        const cart = JSON.parse(localStorage.getItem("tutuCart") || "[]");

        if (Array.isArray(cart)) {
            return cart;
        }

        // If old/invalid cart data is stored
        localStorage.removeItem("tutuCart");
        return [];
    } catch {
        localStorage.removeItem("tutuCart");
        return [];
    }
}
function saveCart(cart) {
    localStorage.setItem("tutuCart", JSON.stringify(cart));
    updateCartCount();
}
function updateCartCount() {
    const el = document.getElementById("cartCount");
    if (el) el.textContent = getCart().reduce((sum, item) => sum + Number(item.quantity || 0), 0);
}
function addProductToCart(product_id, product_name, price, image_url) {
    const size = document.getElementById("size")?.value || "";
    const color = document.getElementById("color")?.value || "";
    const cart = getCart();
    const existing = cart.find(item => item.product_id === product_id && item.size === size && item.color === color);
    if (existing) existing.quantity += 1;
    else cart.push({product_id, product_name, price: Number(price), image_url, size, color, quantity: 1});
    saveCart(cart);
    alert("Product added to cart.");
}
function renderCart() {
    const wrap = document.getElementById("cartItems");
    const summary = document.getElementById("cartSummary");
    if (!wrap || !summary) return;
    const cart = getCart();
    if (!cart.length) {
        wrap.innerHTML = '<div class="empty-state">Your cart is empty.</div>';
        summary.innerHTML = '<a class="btn primary" href="/products">Shop Products</a>';
        return;
    }
    let total = 0;
    wrap.innerHTML = cart.map((item, i) => {
        const line = Number(item.price) * Number(item.quantity);
        total += line;
        return `<div class="cart-row">
            <div><strong>${escapeHtml(item.product_name)}</strong><small>${escapeHtml(item.size || "No size")} · ${escapeHtml(item.color || "No color")}</small></div>
            <div>₹${line.toFixed(2)}</div>
            <div class="qty"><button onclick="changeQty(${i},-1)">−</button><span>${item.quantity}</span><button onclick="changeQty(${i},1)">+</button></div>
            <button class="link-danger" onclick="removeCartItem(${i})">Remove</button>
        </div>`;
    }).join("");
    summary.innerHTML = `<div><span>Total</span><strong>₹${total.toFixed(2)}</strong></div>
        <a class="btn primary" href="/checkout">Proceed to Checkout</a>`;
}
function changeQty(index, delta) {
    const cart = getCart();
    cart[index].quantity = Math.max(1, Number(cart[index].quantity) + delta);
    saveCart(cart); renderCart();
}
function removeCartItem(index) {
    const cart = getCart(); cart.splice(index, 1); saveCart(cart); renderCart();
}
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
document.addEventListener("DOMContentLoaded", () => {

    updateCartCount();
    renderCart();

    const addButton = document.getElementById("addToCartButton");

    if (addButton) {

        addButton.addEventListener("click", () => {

            const productId = Number(addButton.dataset.productId);
            const productName = addButton.dataset.productName;
            const price = Number(addButton.dataset.price);
            const imageUrl = addButton.dataset.imageUrl || "";

            addProductToCart(
                productId,
                productName,
                price,
                imageUrl
            );

        });

    }

});