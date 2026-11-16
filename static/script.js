document.addEventListener("DOMContentLoaded", function () {
  const search = document.getElementById("tableSearch");
  if (search) {
    search.addEventListener("input", function () {
      const term = search.value.toLowerCase();
      document.querySelectorAll("#productsTable tbody tr").forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(term) ? "" : "none";
      });
    });
  }
});
