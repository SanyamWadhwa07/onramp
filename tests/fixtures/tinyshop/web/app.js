const API = "http://localhost:8000";

async function loadProducts() {
  const res = await fetch(API + "/products");
  const products = await res.json();
  const list = document.getElementById("products");
  list.innerHTML = products
    .map((p) => `<li><label><input type="checkbox" value="${p.sku}"> ${p.name}</label></li>`)
    .join("");
}

async function buy() {
  const skus = [...document.querySelectorAll("input:checked")].map((el) => el.value);
  const res = await fetch(API + "/orders", { method: "POST", body: JSON.stringify(skus) });
  const order = await res.json();
  document.getElementById("status").textContent = res.ok
    ? `Order #${order.id}: ${(order.total_cents / 100).toFixed(2)}`
    : order.error;
}

document.getElementById("buy").addEventListener("click", buy);
loadProducts();
