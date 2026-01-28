

/* ===============================
   NURSE REPORT – AUTO MODE
   =============================== */

/* ========= CORE ========= */

function num(v) {
    const n = parseFloat(v);
    return isNaN(n) ? 0 : n;
}

/* ========= CALC PER DAY ========= */

function calcDay(day) {
    calcDepartments(day);
    calcHospital(day);
}
/* ===============================
   AUTO SAVE – DEBOUNCE
   =============================== */

let saveTimer = null;

document.addEventListener("input", e => {
    const el = e.target;

    if (!el.classList.contains("autosave")) return;

    // debounce
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
        autoSave(el);
    }, 600);
});

function autoSave(el) {
    const payload = {
        day: el.dataset.day,
        khoa: el.dataset.khoa || null,
        type: el.dataset.type,
        scope: el.dataset.scope,
        value: el.value,
        month: document.getElementById("monthSelect").value,
        year: document.getElementById("yearSelect").value
    };

    fetch("/api/nurse-report/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(r => {
        if (r.ok) {
            el.classList.add("saved");
            setTimeout(() => el.classList.remove("saved"), 800);
        }
    })
    .catch(err => console.error("Auto-save lỗi:", err));
}
function makeKey(el) {
    const m = document.getElementById("monthSelect").value;
    const y = document.getElementById("yearSelect").value;

    return [
        "nurseReport",
        y,
        m,
        el.dataset.day,
        el.dataset.khoa || "ALL",
        el.dataset.type,
        el.dataset.scope
    ].join(":");
}

function saveLocal(el) {
    const key = makeKey(el);
    localStorage.setItem(key, el.value);
}
function loadLocal() {
    clearForm(); // 👈 quan trọng

    document.querySelectorAll("input.autosave").forEach(el => {
        const key = makeKey(el);
        const v = localStorage.getItem(key);

        if (v !== null) {
            el.value = v;
        }
    });

    // tính lại toàn bảng
    const days = [...new Set(
        Array.from(document.querySelectorAll("input[data-day]"))
            .map(i => i.dataset.day)
    )];
    days.forEach(d => calcDay(d));
}

function clearForm() {
    document.querySelectorAll("input[data-day]").forEach(el => {
        if (el.type === "text" || el.type === "number") {
            el.value = "";
        }
    });
}

/* ========= CALC PER DEPARTMENT ========= */

function calcDepartments(day) {

    // Lấy tất cả ô BN của khoa trong ngày
    const patients = document.querySelectorAll(
        `input[data-day="${day}"][data-scope="dept"][data-type="patient"]`
    );

    patients.forEach(p => {
        const khoa = p.dataset.khoa;

        const n = document.querySelector(
            `input[data-day="${day}"][data-scope="dept"][data-type="nurse"][data-khoa="${khoa}"]`
        );

        const r = document.querySelector(
            `input[data-day="${day}"][data-scope="dept"][data-type="ratio"][data-khoa="${khoa}"]`
        );

        if (!n || !r) return;

        const pv = num(p.value);
        const nv = num(n.value);

        r.value = pv === 0 ? "—" : (nv / pv).toFixed(2);
    });
}

function lockOtherDepartments() {
    const userKhoa = document.body.dataset.userKhoa;

    // không có khoa → coi như admin (không khóa)
    if (!userKhoa) return;

    document.querySelectorAll(
        "input[data-scope='dept']"
    ).forEach(input => {
        const khoa = input.dataset.khoa;

        if (khoa !== userKhoa) {
            input.readOnly = true;
            input.disabled = true;
            input.classList.add("locked-input");
        }
    });
}

/* ========= CALC HOSPITAL ========= */

function calcHospital(day) {

    let totalBN = 0;
    let totalDD = 0;
    let totalLeave = 0;

    document.querySelectorAll(
        `input[data-day="${day}"][data-scope="dept"][data-type="patient"]`
    ).forEach(i => totalBN += num(i.value));

    document.querySelectorAll(
        `input[data-day="${day}"][data-scope="dept"][data-type="nurse"]`
    ).forEach(i => totalDD += num(i.value));

    document.querySelectorAll(
        `input[data-day="${day}"][data-scope="dept"][data-type="leave"]`
    ).forEach(i => totalLeave += num(i.value));

    const p = document.querySelector(
        `input[data-day="${day}"][data-scope="hospital"][data-type="patient-all"]`
    );
    const n = document.querySelector(
        `input[data-day="${day}"][data-scope="hospital"][data-type="nurse-all"]`
    );
    const l = document.querySelector(
        `input[data-day="${day}"][data-scope="hospital"][data-type="leave-all"]`
    );
    const r = document.querySelector(
        `input[data-day="${day}"][data-scope="hospital"][data-type="ratio-all"]`
    );

    if (!p || !n || !r) return;

    p.value = totalBN;
    n.value = totalDD;
    if (l) l.value = totalLeave;

    r.value = totalBN === 0 ? "—" : (totalDD / totalBN).toFixed(2);
}
function updateHeader() {
    const m = document.getElementById("monthSelect").value;
    const y = document.getElementById("yearSelect").value;

    const title = document.getElementById("reportMonthYear");
    if (!title) return;

    title.textContent = `Tháng ${m}/${y}`;
}
document.getElementById("monthSelect")
    .addEventListener("change", updateHeader);

document.getElementById("yearSelect")
    .addEventListener("change", updateHeader);

/* ========= AUTO EVENT (KHÔNG oninput) ========= */


document.addEventListener("DOMContentLoaded", updateHeader);

/* ========= INIT ========= */

document.addEventListener("DOMContentLoaded", () => {
    const userDept = document.body.dataset.userDept;
    const role = document.body.dataset.userRole;

    if (role === "admin") return; // admin gõ tất

    document.querySelectorAll("input[data-scope='dept']").forEach(input => {
        const khoa = input.dataset.khoa;

        if (khoa !== userDept) {
            input.readOnly = true;
            input.classList.add("bg-light");
        }
    });
});


document.addEventListener("input", e => {
    const el = e.target;
    if (!el.classList.contains("autosave")) return;

    saveLocal(el);          // 👈 LƯU LOCAL
    calcDay(el.dataset.day);
});
document.addEventListener("DOMContentLoaded", loadLocal);

document.getElementById("monthSelect").addEventListener("change", loadLocal);
document.getElementById("yearSelect").addEventListener("change", loadLocal);

/* ========= EVENTS ========= */

document.getElementById("monthSelect").addEventListener("change", () => {
    updateHeader();
    loadLocal();
});

document.getElementById("yearSelect").addEventListener("change", () => {
    updateHeader();
    loadLocal();
});
document.addEventListener("DOMContentLoaded", () => {
    lockOtherDepartments();

    const days = [...new Set(
        Array.from(document.querySelectorAll("input[data-day]"))
            .map(i => i.dataset.day)
    )];
    days.forEach(d => calcDay(d));
});

