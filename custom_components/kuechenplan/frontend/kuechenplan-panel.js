// Sidebar panel of the Küchenplan integration: week, cooking, shopping, inventory.
const BASE = "/kuechenplan_static";

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );

const parseDay = (iso) => {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
};
const dayShort = (iso) =>
  parseDay(iso).toLocaleDateString("de-DE", { weekday: "short" }).replace(".", "");
const dayLong = (iso) =>
  parseDay(iso).toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
const weekdayName = (iso) =>
  parseDay(iso).toLocaleDateString("de-DE", { weekday: "long" });
const daysUntil = (iso, today) =>
  Math.round((parseDay(iso) - parseDay(today)) / 86400000);

const fmtNumber = (value) =>
  (Math.round(value * 100) / 100).toString().replace(".", ",");
const FRACTIONS = { 25: "¼", 33: "⅓", 50: "½", 67: "⅔", 75: "¾" };
const fmtKitchen = (value) => {
  const whole = Math.floor(value + 0.005);
  const rest = FRACTIONS[Math.round((value - whole) * 100)];
  return rest ? `${whole || ""}${rest}` : fmtNumber(value);
};
const fmtAmount = (amount, unit) => {
  if (amount === null || amount === undefined) return unit || "";
  if (unit === "g" && amount >= 1000) return `${fmtNumber(amount / 1000)} kg`;
  if (unit === "ml" && amount >= 1000) return `${fmtNumber(amount / 1000)} l`;
  if (unit === "g" || unit === "ml") return `${fmtNumber(amount)} ${unit}`;
  return unit ? `${fmtKitchen(amount)} ${unit}` : fmtKitchen(amount);
};
const stepSize = (amount, unit) => {
  if (unit === "g" || unit === "ml") return amount > 200 ? 50 : 10;
  return 1;
};
const expiryLabel = (iso, today) => {
  const left = daysUntil(iso, today);
  if (left < 0) return "abgelaufen";
  if (left === 0) return "heute";
  if (left === 1) return "morgen";
  return `in ${left} Tagen`;
};

const icon = (path, size = 26) =>
  `<svg aria-hidden="true" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
const ICONS = {
  menu: '<path d="M4 7h16M4 12h16M4 17h16"></path>',
  woche: '<rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M3 10h18M8 3v4M16 3v4"></path>',
  kochen: '<path d="M4 11h16v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"></path><path d="M2 11h20M9 7c0-2 2-2 2-4M14 7c0-2 2-2 2-4"></path>',
  einkauf: '<path d="M5 8h14l-1 13H6z"></path><path d="M9 8V6a3 3 0 0 1 6 0v2"></path>',
  kuehlschrank: '<rect x="6" y="2" width="12" height="20" rx="2"></rect><path d="M6 10h12M9 5v2M9 13v3"></path>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"></path>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"></path>',
  clock: '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
  swap: '<path d="M7 4v14M7 18l-3-3M7 18l3-3M17 20V6M17 6l-3 3M17 6l3 3"></path>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"></path>',
  close: '<path d="M6 6l12 12M18 6L6 18"></path>',
  rezepte: '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"></path><path d="M5 17a3 3 0 0 1 3-3h11M9 8h6"></path>',
};

const STYLE = `
:host {
  --ground: #f3f4f1; --surface: #ffffff; --ink: #16201b; --muted: #4e5a53;
  --line: #e7e9e4; --mustard: #f2c230; --on-mustard: #16201b;
  --tomato: #c8321a; --tomato-text: #b02a14; --basil: #1d6a47;
  --offer-bg: #dcebe2; --offer-ink: #124a31; --rail: #16201b; --on-rail: #f3f4f1;
  display: block; height: 100%; background: var(--ground); color: var(--ink);
  font-family: "Instrument Sans", system-ui, sans-serif; -webkit-font-smoothing: antialiased;
}
:host([dark]) {
  --ground: #101613; --surface: #1c2621; --ink: #f0f2ee; --muted: #aab4ad;
  --line: #2c3932; --tomato-text: #ff8a73; --offer-bg: #1d3a2c; --offer-ink: #a9e0c3;
  --basil: #3f9a70; --rail: #0a0f0c;
}
* { box-sizing: border-box; }
button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; border: 0; background: none; }
button:disabled { opacity: 0.45; cursor: default; }
button:focus-visible, input:focus-visible, select:focus-visible {
  outline: 3px solid var(--tomato); outline-offset: 2px;
}
h1, h2, p, ul { margin: 0; padding: 0; }
ul { list-style: none; }
.display { font-family: "Bricolage Grotesque", sans-serif; letter-spacing: -0.02em; }
.app { display: flex; height: 100%; }
.rail {
  width: 96px; flex-shrink: 0; padding: 12px 0; display: flex; flex-direction: column;
  align-items: center; gap: 8px; background: var(--rail); color: var(--on-rail); overflow-y: auto;
}
.rail button {
  width: 80px; height: 76px; flex-shrink: 0; border-radius: 14px; color: inherit; display: flex;
  flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  font-size: 13px; font-weight: 600;
}
.rail button.menu { height: 48px; }
.rail button[aria-current="page"] { background: var(--mustard); color: var(--on-mustard); }
.content { flex: 1; min-width: 0; overflow-y: auto; }

.week {
  min-height: 100%; padding: 24px; display: grid; gap: 16px;
  grid-template-columns: minmax(0, 11fr) minmax(0, 13fr);
  grid-template-rows: minmax(0, 1fr) auto;
}
.hero {
  background: var(--mustard); color: var(--on-mustard); border-radius: 22px; padding: 32px;
  display: flex; flex-direction: column; min-height: 420px;
}
.hero .when { font-size: 20px; font-weight: 600; }
.hero h1 {
  margin-top: 28px; font-size: clamp(52px, 7vw, 92px); line-height: 0.94; letter-spacing: -0.03em;
  font-weight: 800; overflow-wrap: break-word; hyphens: manual;
}
.hero h1.long { font-size: clamp(40px, 4.8vw, 62px); line-height: 1; }
.hero .about { margin-top: 22px; font-size: 21px; line-height: 1.35; }
.hero .rice { margin-top: 18px; display: flex; align-items: center; gap: 10px; font-size: 17px; font-weight: 600; }
.hero .spacer { flex: 1; min-height: 20px; }
.primary {
  min-height: 72px; padding: 0 24px; border-radius: 16px; background: #16201b; color: #f3f4f1;
  display: flex; align-items: center; justify-content: center; gap: 12px; font-size: 22px; font-weight: 700;
}
.days { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.day {
  flex: 1; min-height: 88px; background: var(--surface); border-radius: 18px; display: flex;
  align-items: stretch; overflow: hidden;
}
.day.target { outline: 3px dashed var(--tomato); outline-offset: -3px; }
.day.source { background: var(--mustard); color: var(--on-mustard); }
.day .open {
  flex: 1; min-width: 0; padding: 10px 8px 10px 24px; display: flex; align-items: center; gap: 20px; text-align: left;
}
.day .short { width: 64px; flex-shrink: 0; font-size: 34px; font-weight: 700; }
.day .text { flex: 1; min-width: 0; }
.day .title { display: block; font-size: 27px; font-weight: 700; letter-spacing: -0.01em; overflow-wrap: anywhere; }
.day .open-slot { color: var(--muted); }
.day .sub { display: block; margin-top: 3px; font-size: 16px; color: var(--muted); }
.day.source .sub { color: inherit; }
.day .swap { width: 64px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--muted); }
.chip {
  display: inline-block; padding: 5px 11px; border-radius: 99px; background: var(--offer-bg);
  color: var(--offer-ink); font-size: 13px; font-weight: 700; white-space: nowrap;
}
.done-mark { color: var(--basil); }
.tiles { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.tile {
  background: var(--surface); border-radius: 18px; padding: 20px 24px; display: flex; flex-direction: column;
  justify-content: center; gap: 4px; text-align: left; min-height: 112px;
}
.tile .label { font-size: 15px; font-weight: 600; color: var(--muted); }
.tile .big { font-size: 30px; font-weight: 700; letter-spacing: -0.01em; }
.tile .big.alert { color: var(--tomato-text); }
.tile .small { font-size: 15px; color: var(--muted); }
.tile.dark { background: #16201b; color: #f3f4f1; }
.tile.dark .label, .tile.dark .small { color: #c9d0cb; }
.banner {
  grid-column: 1 / -1; background: var(--tomato); color: #fff; border-radius: 18px; padding: 14px 24px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px; font-size: 18px; font-weight: 600;
}
.banner button { min-height: 44px; padding: 0 16px; border-radius: 10px; background: rgba(0, 0, 0, 0.22); color: #fff; font-weight: 700; }

.cook { min-height: 100%; display: flex; background: #16201b; color: #f3f4f1; }
.cook aside { width: 400px; flex-shrink: 0; padding: 28px; display: flex; flex-direction: column; gap: 18px; background: #212d27; }
.cook .back { display: flex; align-items: center; gap: 8px; min-height: 44px; font-size: 17px; font-weight: 600; }
.cook h1 { font-size: 40px; line-height: 1; font-weight: 800; overflow-wrap: anywhere; }
.stepper { display: flex; align-items: center; justify-content: space-between; padding: 8px 8px 8px 16px; border-radius: 14px; background: #16201b; font-size: 17px; font-weight: 600; }
.stepper div { display: flex; gap: 6px; }
.stepper button { width: 48px; height: 48px; border-radius: 10px; background: #33423a; color: #f3f4f1; font-size: 24px; font-weight: 600; }
.ingredients { flex: 1; }
.ingredients li { display: flex; align-items: baseline; gap: 12px; padding: 10px 0; border-bottom: 1px solid #33423a; font-size: 18px; }
.ingredients .amount { width: 92px; flex-shrink: 0; font-weight: 700; color: var(--mustard); font-variant-numeric: tabular-nums; }
.cook main { flex: 1; min-width: 0; padding: 32px 40px; display: flex; flex-direction: column; }
.progress { display: flex; align-items: center; justify-content: space-between; min-height: 44px; font-size: 19px; font-weight: 600; color: #c9d0cb; }
.dots { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.dots span { width: 28px; height: 8px; border-radius: 4px; background: #33423a; }
.dots span.on { background: var(--mustard); }
.step { flex: 1; display: flex; align-items: center; font-family: "Bricolage Grotesque", sans-serif; font-size: clamp(30px, 4.2vw, 54px); line-height: 1.12; letter-spacing: -0.015em; font-weight: 600; padding: 24px 0; }
.timer { margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 12px 12px 24px; border-radius: 16px; background: var(--mustard); color: #16201b; }
.timer.ringing { background: var(--tomato); color: #fff; }
.timer .time { font-family: "Bricolage Grotesque", sans-serif; font-size: 38px; font-weight: 800; font-variant-numeric: tabular-nums; }
.timer button { min-height: 56px; padding: 0 24px; border-radius: 12px; background: #16201b; color: #f3f4f1; font-size: 19px; font-weight: 700; }
.pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 14px; }
.pair button { min-height: 84px; border-radius: 18px; font-size: 22px; font-weight: 700; padding: 8px 16px; }
.pair .quiet { background: #33423a; color: #f3f4f1; }
.pair .loud { background: #f3f4f1; color: #16201b; }
.rate { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 14px; }
.rate h2 { font-family: "Bricolage Grotesque", sans-serif; font-size: 54px; line-height: 1; font-weight: 800; margin-bottom: 18px; }
.rate button { min-height: 84px; border-radius: 18px; background: #33423a; color: #f3f4f1; font-size: 22px; font-weight: 700; }
.rate button.first { background: var(--mustard); color: #16201b; }

.page { max-width: 1120px; margin: 0 auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; min-height: 100%; }
.page h1 { font-size: clamp(38px, 5vw, 52px); line-height: 1; font-weight: 800; letter-spacing: -0.025em; }
.page header.row { display: flex; align-items: center; flex-wrap: wrap; gap: 16px 20px; }
.page header.row > div { flex: 1; min-width: 240px; }
.page header p { margin-top: 8px; font-size: 18px; color: var(--muted); }
.cta { min-height: 64px; padding: 0 28px; border-radius: 16px; background: #16201b; color: #f3f4f1; font-size: 20px; font-weight: 700; }
.ghost { min-height: 64px; padding: 0 24px; border-radius: 16px; background: var(--line); font-size: 18px; font-weight: 700; }
.tabs { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 4px; padding: 4px; border-radius: 14px; background: var(--line); max-width: 520px; }
.tabs button { min-height: 44px; border-radius: 10px; font-size: 16px; font-weight: 700; }
.tabs button[aria-pressed="true"] { background: var(--surface); }
.groups { columns: 2 380px; column-gap: 16px; flex: 1; }
.group { break-inside: avoid; margin-bottom: 16px; }
.group h2 { margin-bottom: 6px; font-size: 14px; font-weight: 700; color: var(--muted); }
.list { background: var(--surface); border-radius: 16px; overflow: hidden; }
.list li + li { border-top: 1px solid var(--ground); }
.item { width: 100%; min-height: 60px; padding: 9px 14px; display: flex; align-items: center; gap: 12px; text-align: left; }
.box { width: 28px; height: 28px; flex-shrink: 0; border-radius: 9px; border: 2.5px solid var(--ink); display: flex; align-items: center; justify-content: center; color: #fff; }
.item.done .box { background: var(--basil); border-color: var(--basil); }
.item .name { display: block; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
.item.done .name { text-decoration: line-through; color: var(--muted); }
.item .detail { display: block; margin-top: 2px; font-size: 13px; color: var(--muted); }
.item .body { flex: 1; min-width: 0; }
.adder { position: sticky; bottom: 0; display: flex; gap: 8px; padding: 10px; border-radius: 16px; background: var(--surface); box-shadow: 0 -1px 0 var(--line); }
.adder input { flex: 1; min-width: 0; height: 48px; padding: 0 14px; border: 0; border-radius: 12px; background: var(--ground); font-size: 16px; }
.adder button { width: 48px; height: 48px; flex-shrink: 0; border-radius: 12px; background: #16201b; color: #f3f4f1; font-size: 24px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.empty { padding: 32px 24px; border-radius: 18px; background: var(--surface); font-size: 18px; line-height: 1.4; color: var(--muted); }

.expiring { background: var(--tomato); color: #fff; border-radius: 18px; padding: 16px 24px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 28px; font-size: 18px; font-weight: 600; }
.expiring strong { font-family: "Bricolage Grotesque", sans-serif; font-size: 24px; font-weight: 700; }
.places { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; align-items: start; flex: 1; }
.place { background: var(--surface); border-radius: 18px; padding: 20px 22px; }
.place h2 { margin-bottom: 8px; font-size: 28px; font-weight: 700; }
.stock { width: 100%; min-height: 48px; padding: 8px 0; display: flex; justify-content: space-between; gap: 12px; text-align: left; font-size: 18px; border-bottom: 1px solid var(--line); }
.stock .what { font-weight: 500; overflow-wrap: anywhere; }
.stock .what.urgent { font-weight: 700; color: var(--tomato-text); }
.stock .qty { flex-shrink: 0; color: var(--muted); font-variant-numeric: tabular-nums; }
.place .none { padding: 10px 0; color: var(--muted); }

.audit { min-height: 100%; padding: 20px 16px 18px; display: flex; flex-direction: column; background: var(--mustard); color: #16201b; }
.audit > * { width: 100%; max-width: 560px; margin-inline: auto; }
.audit .top { display: flex; justify-content: space-between; align-items: center; min-height: 44px; font-size: 16px; font-weight: 700; }
.audit .top button { min-height: 44px; font-weight: 600; color: #16201b; }
.bar { height: 8px; border-radius: 4px; background: rgba(22, 32, 27, 0.18); overflow: hidden; flex-shrink: 0; }
.bar div { height: 100%; background: #16201b; border-radius: 4px; }
.card { flex: 1; margin-top: 18px; padding: 26px 24px; border-radius: 26px; background: #fff; color: #16201b; display: flex; flex-direction: column; }
.card .place-name { font-size: 16px; font-weight: 600; color: #4e5a53; }
.card h1 { margin-top: 10px; font-family: "Bricolage Grotesque", sans-serif; font-size: 56px; line-height: 1; letter-spacing: -0.03em; font-weight: 800; overflow-wrap: anywhere; }
.card .last { margin-top: 14px; font-size: 20px; }
.card .best { margin-top: 4px; font-size: 16px; color: #4e5a53; }
.card .grow { flex: 1; min-height: 20px; }
.card .ask { margin-bottom: 10px; font-size: 16px; font-weight: 600; }
.counter { display: grid; grid-template-columns: 64px minmax(0, 1fr) 64px; gap: 8px; align-items: center; }
.counter button { height: 64px; border-radius: 14px; background: #e7e9e4; color: #16201b; font-size: 30px; font-weight: 600; }
.counter output { text-align: center; font-family: "Bricolage Grotesque", sans-serif; font-size: 36px; font-weight: 800; font-variant-numeric: tabular-nums; }
.answers { margin-top: 14px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 10px; flex-shrink: 0; }
.answers button { min-height: 76px; border-radius: 18px; font-size: 19px; font-weight: 700; }
.answers .gone { border: 2.5px solid #16201b; color: #16201b; }
.answers .ok { background: #16201b; color: #f3f4f1; }
.card p.note { margin-top: 12px; font-size: 17px; line-height: 1.4; color: #4e5a53; }
.card p.sum { margin-top: 16px; font-size: 20px; line-height: 1.35; }
.card label { font-size: 16px; font-weight: 600; }
.card form { margin-top: 8px; display: flex; gap: 8px; }
.card form input { flex: 1; min-width: 0; height: 56px; padding: 0 16px; border: 0; border-radius: 14px; background: #f3f4f1; color: #16201b; font-size: 17px; }
.card form button { width: 56px; height: 56px; flex-shrink: 0; border-radius: 14px; background: #e7e9e4; color: #16201b; font-size: 24px; }
.card .finish { margin-top: 12px; min-height: 72px; border-radius: 18px; background: #16201b; color: #f3f4f1; font-size: 20px; font-weight: 700; }

.recipes { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.recipe { min-height: 104px; padding: 18px 20px; border-radius: 18px; background: var(--surface); display: flex; flex-direction: column; justify-content: center; gap: 4px; text-align: left; }
.recipe .name { font-size: 25px; font-weight: 700; letter-spacing: -0.01em; overflow-wrap: break-word; }
.recipe .meta { font-size: 15px; color: var(--muted); }
.search { width: 100%; height: 56px; padding: 0 18px; border: 0; border-radius: 14px; background: var(--surface); font-size: 17px; }
.need { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--line); font-size: 17px; }
.need .state { flex-shrink: 0; font-size: 14px; font-weight: 700; color: var(--muted); }
.need .state.home { color: var(--basil); }
.dialog .stepper { background: var(--line); }
.dialog .stepper button { background: var(--surface); color: var(--ink); }
.dialog .note { font-size: 16px; line-height: 1.35; color: var(--muted); }
.adhocbar { display: flex; flex-wrap: wrap; gap: 8px; }
.adhocbar button { min-height: 48px; padding: 0 18px; border-radius: 12px; background: var(--mustard); color: var(--on-mustard); font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.day.spontan { background: var(--mustard); color: var(--on-mustard); flex: 0 0 auto; }
.day.spontan .sub, .day.spontan .swap { color: inherit; }
.sheet { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(10, 15, 12, 0.55); }
.dialog { width: 100%; max-width: 460px; max-height: 100%; overflow-y: auto; padding: 24px; border-radius: 22px; background: var(--surface); display: flex; flex-direction: column; gap: 14px; }
.dialog h2 { font-size: 30px; font-weight: 800; letter-spacing: -0.02em; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 15px; font-weight: 600; flex: 1; min-width: 0; }
.field input, .field select { width: 100%; height: 52px; padding: 0 14px; border: 0; border-radius: 12px; background: var(--ground); font-size: 17px; font-weight: 400; }
.fields { display: flex; gap: 10px; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
.actions button { flex: 1 1 120px; min-height: 56px; border-radius: 14px; font-size: 17px; font-weight: 700; background: var(--line); }
.actions .main { background: #16201b; color: #f3f4f1; }
.actions .danger { color: var(--tomato-text); }
.toast { position: fixed; left: 50%; bottom: 96px; transform: translateX(-50%); z-index: 20; max-width: calc(100% - 32px); padding: 14px 20px; border-radius: 14px; background: var(--tomato); color: #fff; font-size: 16px; font-weight: 600; }
.loading { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 18px; color: var(--muted); }

@media (max-width: 900px) {
  .week { grid-template-columns: minmax(0, 1fr); grid-template-rows: none; padding: 16px; }
  .hero { min-height: 340px; padding: 24px; }
  .tiles { grid-template-columns: minmax(0, 1fr); }
  .places { grid-template-columns: minmax(0, 1fr); }
  .page { padding: 16px; }
  .cook { flex-direction: column; }
  .cook aside { width: 100%; padding: 16px; }
  .cook main { padding: 16px; min-height: 70dvh; }
}
@media (max-width: 640px) {
  .app { flex-direction: column-reverse; }
  .rail { width: 100%; flex-direction: row; justify-content: space-around; overflow: visible; flex-shrink: 0; }
  .rail button, .rail button.menu { width: auto; min-width: 0; padding: 0; }
}

#root { height: 100%; }
button { touch-action: manipulation; -webkit-tap-highlight-color: transparent; transition: transform 90ms ease-out; }
button:active:not(:disabled) { transform: scale(0.98); }
.content { display: flex; flex-direction: column; padding-top: var(--safe-area-inset-top, 0px); padding-right: var(--safe-area-inset-right, 0px); overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.content > * { flex: 1 0 auto; }
.content.v-kochen { background: #16201b; }
.content.v-inventur { background: var(--mustard); }
.rail { padding-top: calc(12px + var(--safe-area-inset-top, 0px)); padding-left: var(--safe-area-inset-left, 0px); box-sizing: content-box; }
.weekbar, .cookbar, .cooktabs { display: none; }
.timer .which { display: block; font-size: 14px; font-weight: 600; }
.recipe .state { font-size: 15px; font-weight: 700; color: var(--muted); }
.recipe .state.ready { color: var(--basil); }
.recipe .state.soon { color: var(--tomato-text); }
.section-title { margin-top: 4px; font-size: 14px; font-weight: 700; color: var(--muted); }
.need .state.maybe { color: var(--tomato-text); }

@media (max-width: 640px) {
  .app.focus .rail { display: none; }
  .content.v-kochen, .content.v-inventur { padding-bottom: var(--safe-area-inset-bottom, 0px); }
  .rail { box-sizing: border-box; padding: 6px 6px calc(6px + var(--safe-area-inset-bottom, 0px)); gap: 2px; }
  .rail button.menu { display: none; }
  .rail button { flex: 1 1 0; height: 54px; border-radius: 12px; font-size: 11px; gap: 3px; }
  .rail button svg { width: 23px; height: 23px; }

  .weekbar { display: flex; align-items: center; gap: 4px; min-height: 44px; margin: -4px 0 -4px -10px; grid-column: 1 / -1; }
  .weekbar button { width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; }
  .weekbar span { font-size: 24px; font-weight: 800; }
  .week { display: flex; flex-direction: column; gap: 10px; padding: 8px 16px 16px; }
  .hero { flex: none; min-height: 0; padding: 20px; border-radius: 20px; }
  .hero .when { font-size: 15px; }
  .hero h1 { margin-top: 10px; font-size: 48px; line-height: 0.98; }
  .hero h1.long { font-size: 34px; line-height: 1.04; }
  .hero .about { margin-top: 10px; font-size: 16px; }
  .hero .rice { margin-top: 10px; font-size: 15px; }
  .hero .spacer { min-height: 14px; }
  .primary { min-height: 58px; border-radius: 14px; font-size: 19px; }
  .days { gap: 8px; }
  .day { flex: none; min-height: 68px; border-radius: 16px; }
  .day .open { padding: 8px 4px 8px 16px; gap: 10px; }
  .day .short { width: 40px; font-size: 23px; }
  .day .title { font-size: 19px; line-height: 1.15; }
  .day .sub { font-size: 14px; margin-top: 2px; }
  .day .swap { width: 48px; }
  .chip { padding: 4px 9px; font-size: 12px; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .tile { min-height: 92px; padding: 14px 16px; border-radius: 16px; }
  .tile.dark { grid-column: 1 / -1; min-height: 76px; }
  .tile .label { font-size: 13px; }
  .tile .big { font-size: 21px; line-height: 1.1; }
  .tile .small { font-size: 13px; }
  .banner { padding: 12px 16px; font-size: 16px; flex-wrap: wrap; }

  .page { padding: 12px 16px 16px; gap: 12px; }
  .page h1 { font-size: 34px; }
  .page header p { font-size: 15px; margin-top: 4px; }
  .page header.row { gap: 10px; }
  .page header.row > div { flex: 1 0 100%; }
  .cta, .ghost { flex: 1 1 0; min-height: 54px; padding: 0 12px; font-size: 16px; border-radius: 14px; }
  .tabs { max-width: none; }
  .groups { columns: auto; }
  .list { border-radius: 14px; }
  .adder { margin: 0 -16px -16px; padding: 10px 16px; border-radius: 0; }
  .recipes { grid-template-columns: minmax(0, 1fr); gap: 8px; }
  .recipe { min-height: 76px; padding: 14px 16px; border-radius: 16px; }
  .recipe .name { font-size: 21px; }
  .place { padding: 14px 16px; border-radius: 16px; }
  .place h2 { font-size: 22px; }
  .stock { font-size: 17px; }
  .expiring { padding: 12px 16px; font-size: 16px; border-radius: 16px; }
  .expiring strong { flex: 1 0 100%; font-size: 19px; }

  .cook { flex-direction: column; }
  .content.v-kochen { background: #212d27; }
  .cookbar { display: flex; align-items: center; gap: 4px; padding: 4px 16px 4px 6px; background: #212d27; }
  .cookbar button { width: 44px; height: 44px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: #f3f4f1; }
  .cookbar span { font-size: 20px; font-weight: 700; line-height: 1.1; overflow-wrap: break-word; min-width: 0; }
  .cooktabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; padding: 0 16px 10px; background: #212d27; }
  .cooktabs button { min-height: 44px; border-radius: 10px; color: #c9d0cb; font-size: 16px; font-weight: 700; }
  .cooktabs button[aria-pressed="true"] { background: #33423a; color: #f3f4f1; }
  .cook aside { width: 100%; padding: 12px 16px 20px; flex: 1 0 auto; }
  .cook aside .back, .cook aside h1 { display: none; }
  .cook[data-tab="steps"] aside { display: none; }
  .cook[data-tab="zutaten"] main { display: none; }
  .cook main { padding: 8px 16px 16px; min-height: 0; flex: 1 0 auto; }
  .progress { font-size: 15px; min-height: 32px; }
  .dots span { width: 18px; height: 6px; }
  .step { font-size: 32px; line-height: 1.16; padding: 16px 0; }
  .timer { margin-bottom: 10px; padding: 8px 8px 8px 18px; border-radius: 14px; }
  .timer .time { font-size: 30px; }
  .timer button { min-height: 52px; padding: 0 18px; font-size: 17px; }
  .pair { gap: 10px; }
  .pair button { min-height: 68px; font-size: 19px; border-radius: 16px; }
  .rate h2 { font-size: 42px; }
  .rate button { min-height: 68px; font-size: 19px; }

  .audit { padding: 8px 16px 12px; }
  .card { margin-top: 12px; padding: 22px 20px; }
  .card h1 { font-size: 46px; }

  .sheet { align-items: flex-end; padding: 0; }
  .dialog { max-width: none; max-height: 90%; border-radius: 22px 22px 0 0; padding: 22px 16px calc(16px + var(--safe-area-inset-bottom, 0px)); }
  .actions button { flex: 1 1 100%; }
  .toast { bottom: calc(76px + var(--safe-area-inset-bottom, 0px)); }
}
`;

const FONT_FACES = `
@font-face { font-family: "Bricolage Grotesque"; src: url(${BASE}/fonts/bricolage-grotesque.woff2) format("woff2"); font-weight: 400 800; font-display: swap; }
@font-face { font-family: "Instrument Sans"; src: url(${BASE}/fonts/instrument-sans.woff2) format("woff2"); font-weight: 400 700; font-display: swap; }
`;

class KuechenplanPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><div id="root"><div class="loading">Küchenplan lädt…</div></div>`;
    this._root = this.shadowRoot.getElementById("root");
    const params = new URLSearchParams(window.location.search);
    this._view = ["woche", "kochen", "rezepte", "einkauf", "kuehlschrank"].includes(params.get("view"))
      ? params.get("view")
      : "woche";
    this._store = params.get("store");
    this._data = null;
    this._swapFrom = null;
    this._cook = null;
    this._audit = null;
    this._edit = null;
    this._recipe = null;
    this._recipeQuery = "";
    this.shadowRoot.addEventListener("click", (event) => this._onClick(event));
    this.shadowRoot.addEventListener("input", (event) => {
      if (event.target.name === "recipe-search") {
        this._recipeQuery = event.target.value;
        this._render();
      }
    });
    this.shadowRoot.addEventListener("submit", (event) => this._onSubmit(event));
  }

  connectedCallback() {
    if (!document.getElementById("kuechenplan-fonts")) {
      const style = document.createElement("style");
      style.id = "kuechenplan-fonts";
      style.textContent = FONT_FACES;
      document.head.append(style);
    }
    this._subscribe();
  }

  disconnectedCallback() {
    this._unsubscribe?.then((off) => off()).catch(() => {});
    this._unsubscribe = null;
    this._stopTimer();
    this._releaseWake();
  }

  set hass(hass) {
    this._hass = hass;
    this.toggleAttribute("dark", Boolean(hass?.themes?.darkMode));
    this._subscribe();
  }

  set narrow(_) {}
  set route(_) {}
  set panel(_) {}

  _subscribe() {
    if (!this._hass || !this.isConnected || this._unsubscribe) return;
    this._unsubscribe = this._hass.connection.subscribeMessage(
      (data) => {
        this._data = data;
        this._render();
      },
      { type: "kuechenplan/subscribe" },
    );
  }

  async _call(operation, args = {}) {
    try {
      return await this._hass.connection.sendMessagePromise({
        type: "kuechenplan/call",
        operation,
        args,
      });
    } catch (err) {
      this._toast(err.message || "Das hat nicht geklappt.");
      return null;
    }
  }

  _toast(text) {
    this._toastText = text;
    this._render();
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toastText = null;
      this._render();
    }, 4000);
  }

  // --- Rendering ---

  _render() {
    if (!this._data) return;
    const scroller = this._root.querySelector(".content");
    const scroll = scroller ? scroller.scrollTop : 0;
    const active = this.shadowRoot.activeElement;
    const focusName = active?.tagName === "INPUT" ? active.name : null;
    const typed = Object.fromEntries(
      [...this._root.querySelectorAll("input[name]")].map((input) => [input.name, input.value]),
    );

    this._root.innerHTML = `
      <div class="app ${this._view === "kochen" || this._view === "inventur" ? "focus" : ""}">
        ${this._renderNav()}
        <div class="content v-${this._view}">${this._renderView()}</div>
      </div>
      ${this._edit ? this._renderEdit() : ""}
      ${this._recipe ? this._renderRecipeSheet() : ""}
      ${this._toastText ? `<div class="toast" role="alert">${esc(this._toastText)}</div>` : ""}`;

    // A live update must not eat what someone is typing.
    for (const input of this._root.querySelectorAll("input[name]")) {
      if (typed[input.name] !== undefined) input.value = typed[input.name];
    }
    const content = this._root.querySelector(".content");
    if (content) content.scrollTop = scroll;
    if (focusName) this._root.querySelector(`input[name="${focusName}"]`)?.focus();
  }

  _renderNav() {
    const entries = [
      ["woche", "Woche"],
      ["kochen", "Kochen"],
      ["rezepte", "Rezepte"],
      ["einkauf", "Einkauf"],
      ["kuehlschrank", "Kühlschrank"],
    ];
    const current = this._view === "inventur" ? "kuehlschrank" : this._view;
    return `<nav class="rail" aria-label="Bereiche">
      <button type="button" class="menu" data-action="menu" aria-label="Home-Assistant-Menü">${icon(ICONS.menu)}</button>
      ${entries
        .map(
          ([view, label]) => `<button type="button" data-action="view" data-value="${view}" ${current === view ? 'aria-current="page"' : ""}>
            ${icon(ICONS[view])}${label}</button>`,
        )
        .join("")}
    </nav>`;
  }

  _renderView() {
    switch (this._view) {
      case "kochen":
        return this._renderCook();
      case "rezepte":
        return this._renderRecipes();
      case "einkauf":
        return this._renderShopping();
      case "kuehlschrank":
        return this._renderInventory();
      case "inventur":
        return this._renderAudit();
      default:
        return this._renderWeek();
    }
  }

  _heroDay() {
    const { days, today } = this._data;
    return days.find((day) => day.date >= today && day.status === "planned");
  }

  _renderWeek() {
    const { today, days, plan_weekdays: weekdays } = this._data;
    const hero = this._heroDay();
    const rows = [];
    const start = hero ? parseDay(hero.date) : parseDay(today);
    for (let offset = 1; rows.length < 6 && offset <= 14; offset += 1) {
      const when = new Date(start);
      when.setDate(start.getDate() + offset);
      const iso = [
        when.getFullYear(),
        String(when.getMonth() + 1).padStart(2, "0"),
        String(when.getDate()).padStart(2, "0"),
      ].join("-");
      const day = days.find((item) => item.date === iso);
      const weekday = (when.getDay() + 6) % 7;
      if (day || weekdays.includes(weekday)) rows.push({ iso, day });
      if (rows.length >= 4 && weekday === 6) break;
    }
    const swapping = this._swapFrom;
    const swapHero = hero && !swapping;
    return `<div class="week">
      <div class="weekbar"><button type="button" data-action="menu" aria-label="Home-Assistant-Menü">${icon(ICONS.menu)}</button><span class="display">Küchenplan</span></div>
      ${swapping ? `<div class="banner" role="status"><span>${esc(dayLong(swapping))}: Mit welchem Tag tauschen?</span><button type="button" data-action="swap-cancel">Abbrechen</button></div>` : ""}
      ${this._renderHero(hero)}
      <section class="days" aria-label="Weitere Tage">
        ${this._data.adhoc.map((meal) => this._renderAdhocRow(meal)).join("")}
        ${swapHero || !hero ? "" : this._renderDayRow(hero.date, hero)}
        ${rows.map(({ iso, day }) => this._renderDayRow(iso, day)).join("")}
      </section>
      ${this._renderTiles()}
    </div>`;
  }

  _renderHero(day) {
    const { today } = this._data;
    if (!day) {
      return `<section class="hero">
        <p class="when">Für die nächsten Tage</p>
        <h1 class="display">Noch kein Plan</h1>
        <p class="about">Sag Claude einfach: „Plan uns die nächste Woche.“ Hier erscheint dann alles von selbst.</p>
      </section>`;
    }
    const isToday = day.date === today;
    const when = isToday ? `Heute, ${dayLong(day.date)}` : `Als Nächstes, ${dayLong(day.date)}`;
    const about = [
      day.recipe?.summary,
      [day.minutes ? `${day.minutes} Minuten` : null, day.servings ? `${day.servings} Portionen` : null]
        .filter(Boolean)
        .join(", "),
      day.note,
    ]
      .filter(Boolean)
      .map(esc)
      .join("<br>");
    let action = "";
    if (day.recipe) {
      action = `<button type="button" class="primary" data-action="cook" data-value="${esc(day.date)}">${isToday ? "Jetzt kochen" : "Rezept ansehen"}${icon(ICONS.arrow, 24)}</button>`;
    } else if (isToday) {
      action = `<button type="button" class="primary" data-action="done-plain" data-value="${esc(day.date)}">Erledigt</button>`;
    }
    return `<section class="hero">
      <p class="when">${esc(when)}</p>
      <h1 class="display ${day.title.length > 12 ? "long" : ""}">${esc(day.title)}</h1>
      ${about ? `<p class="about">${about}</p>` : ""}
      ${day.rice ? `<p class="rice">${icon(ICONS.clock, 22)}Reiskocher rechtzeitig anwerfen</p>` : ""}
      <div class="spacer"></div>
      ${action}
    </section>`;
  }

  _renderDayRow(iso, day) {
    const swapping = this._swapFrom;
    const isSource = swapping === iso;
    const classes = ["day", isSource ? "source" : "", swapping && !isSource ? "target" : ""].join(" ");
    const short = esc(dayShort(iso));
    if (!day) {
      return `<div class="${classes}">
        <button type="button" class="open" data-action="${swapping ? "swap-to" : "noop"}" data-value="${iso}">
          <span class="short display">${short}</span>
          <span class="text"><span class="title display open-slot">Noch offen</span></span>
        </button>
      </div>`;
    }
    const action = swapping ? "swap-to" : day.recipe ? "cook" : "swap-start";
    const sub = [day.minutes ? `${day.minutes} Min.` : null, day.note || null]
      .filter(Boolean)
      .join(" · ");
    let mark = "";
    if (day.status === "cooked") {
      mark = `<span class="done-mark" aria-label="Gekocht">${icon(ICONS.check, 24)}</span>`;
    } else if (day.offers?.length) {
      mark = '<span class="chip">Angebot</span>';
    }
    return `<div class="${classes}">
      <button type="button" class="open" data-action="${action}" data-value="${iso}">
        <span class="short display">${short}</span>
        <span class="text">
          <span class="title display">${esc(day.title)}</span>
          ${sub ? `<span class="sub">${esc(sub)}</span>` : ""}
        </span>
        ${mark}
      </button>
      ${swapping ? "" : `<button type="button" class="swap" data-action="swap-start" data-value="${iso}" aria-label="${esc(day.title)} auf einen anderen Tag legen">${icon(ICONS.swap, 24)}</button>`}
    </div>`;
  }

  _renderAdhocRow(meal) {
    return `<div class="day spontan">
      <button type="button" class="open" data-action="cook-adhoc" data-value="${esc(meal.id)}">
        <span class="text">
          <span class="title display">${esc(meal.title)}</span>
          <span class="sub">Spontan · ${esc(meal.minutes)} Min. · ${esc(meal.servings)} Portionen</span>
        </span>
        ${icon(ICONS.arrow, 24)}
      </button>
      <button type="button" class="swap" data-action="adhoc-remove" data-value="${esc(meal.id)}" aria-label="${esc(meal.title)} streichen">${icon(ICONS.close, 24)}</button>
    </div>`;
  }

  _renderTiles() {
    const { shopping, stores, expiring, audit, inventory, plan_missing: missing, next_plan_day: next, today } = this._data;
    const open = shopping.filter((item) => !item.done);
    const perStore = stores
      .map((store) => `${store.name} ${open.filter((item) => item.store === store.id).length}`)
      .join(", ");
    let auditLabel = `Letzte Inventur vor ${audit.days_since} ${audit.days_since === 1 ? "Tag" : "Tagen"}`;
    if (audit.days_since === null) auditLabel = "Noch keine Inventur";
    else if (audit.days_since === 0) auditLabel = "Inventur war heute";
    const hint =
      missing && daysUntil(next, today) <= 3
        ? `Ab ${weekdayName(next)} fehlt der Plan`
        : "Dauert nur ein paar Minuten";
    return `<div class="tiles">
      <button type="button" class="tile" data-action="view" data-value="einkauf">
        <span class="label">Einkauf</span>
        <span class="big display">${open.length} Artikel offen</span>
        <span class="small">${esc(perStore)}</span>
      </button>
      <button type="button" class="tile" data-action="view" data-value="kuehlschrank">
        <span class="label">Kühlschrank</span>
        ${
          expiring.length
            ? `<span class="big display alert">${expiring.length} ${expiring.length === 1 ? "läuft" : "laufen"} bald ab</span>
               <span class="small">${esc(expiring.slice(0, 3).map((item) => item.name).join(", "))}</span>`
            : `<span class="big display">${inventory.length} Sachen da</span>
               <span class="small">Nichts läuft bald ab</span>`
        }
      </button>
      <button type="button" class="tile dark" data-action="audit-start">
        <span class="label">${esc(auditLabel)}</span>
        <span class="big display">Inventur starten</span>
        <span class="small">${esc(hint)}</span>
      </button>
    </div>`;
  }

  // --- Cooking ---

  _renderCook() {
    const { adhoc, days, today } = this._data;
    if (this._cook?.adhocId && !adhoc.some((meal) => meal.id === this._cook.adhocId)) {
      this._cook = null;
    }
    let day;
    if (this._cook) {
      day = this._cook.adhocId
        ? adhoc.find((meal) => meal.id === this._cook.adhocId)
        : days.find((item) => item.date === this._cook.date);
    } else {
      const next = this._heroDay();
      day = next?.date === today && next.recipe ? next : adhoc[0] ?? next;
    }
    if (!day?.recipe) {
      return `<div class="page"><h1 class="display">Kochen</h1>
        <p class="empty">Gerade ist kein Rezept geplant. Sobald ein Plan da ist, geht es hier los.</p></div>`;
    }
    if (!this._cook) {
      this._cook = {
        date: day.date ?? null,
        adhocId: day.date ? null : day.id,
        step: 0,
        servings: day.servings || day.recipe.servings,
        rating: false,
      };
    }
    const { recipe } = day;
    const cook = this._cook;
    const factor = cook.servings / recipe.servings;
    const ingredients = recipe.ingredients
      .map(
        (item) => `<li><span class="amount">${esc(fmtAmount(item.amount === null ? null : item.amount * factor, item.unit))}</span><span>${esc(item.name)}</span></li>`,
      )
      .join("");
    const tab = cook.rating ? "steps" : cook.tab || "steps";
    return `<div class="cook" data-tab="${tab}">
      <div class="cookbar">
        <button type="button" data-action="view" data-value="woche" aria-label="Zur Woche">${icon(ICONS.back, 24)}</button>
        <span class="display">${esc(recipe.name)}</span>
      </div>
      ${
        cook.rating
          ? ""
          : `<div class="cooktabs" role="group" aria-label="Ansicht">
              <button type="button" data-action="cook-tab" data-value="steps" aria-pressed="${tab === "steps"}">Schritte</button>
              <button type="button" data-action="cook-tab" data-value="zutaten" aria-pressed="${tab === "zutaten"}">Zutaten</button>
            </div>`
      }
      <aside>
        <button type="button" class="back" data-action="view" data-value="woche">${icon(ICONS.back, 22)}Zur Woche</button>
        <h1 class="display">${esc(recipe.name)}</h1>
        <div class="stepper"><span>${cook.servings} ${cook.servings === 1 ? "Portion" : "Portionen"}</span>
          <div>
            <button type="button" data-action="servings" data-value="-1" aria-label="Weniger Portionen">−</button>
            <button type="button" data-action="servings" data-value="1" aria-label="Mehr Portionen">+</button>
          </div>
        </div>
        <ul class="ingredients">${ingredients}</ul>
      </aside>
      <main>${cook.rating ? this._renderRating() : this._renderStep(recipe, cook)}</main>
    </div>`;
  }

  _renderStep(recipe, cook) {
    const steps = recipe.steps.length ? recipe.steps : [{ text: "Für dieses Rezept sind keine Schritte hinterlegt." }];
    const index = Math.min(cook.step, steps.length - 1);
    const step = steps[index];
    const last = index === steps.length - 1;
    const dots = steps.map((_, dot) => `<span class="${dot <= index ? "on" : ""}"></span>`).join("");
    let timer = "";
    if (this._timer) {
      // A running timer stays visible on every step, it is what you are waiting for.
      const label = this._timerLabel();
      const ringing = label === null;
      const other = this._timer.step === index ? "" : `<span class="which">Timer aus Schritt ${this._timer.step + 1}</span>`;
      timer = `<div class="timer ${ringing ? "ringing" : ""}" role="timer">
        <span>${other}<span class="time">${ringing ? "Zeit ist um" : label}</span></span>
        <button type="button" data-action="timer-stop">${ringing ? "Okay" : "Stopp"}</button></div>`;
    } else if (step.minutes) {
      timer = `<div class="timer"><span class="time">${step.minutes}:00</span>
        <button type="button" data-action="timer-start" data-value="${step.minutes}">Timer starten</button></div>`;
    }
    return `<div class="progress"><span>Schritt ${index + 1} von ${steps.length}</span>
        <div class="dots" aria-hidden="true">${dots}</div></div>
      <p class="step">${esc(step.text)}</p>
      ${timer}
      <div class="pair">
        <button type="button" class="quiet" data-action="step" data-value="-1" ${index === 0 ? "disabled" : ""}>Zurück</button>
        <button type="button" class="loud" data-action="${last ? "cook-finish" : "step"}" data-value="1">${last ? "Fertig gekocht" : "Weiter"}</button>
      </div>`;
  }

  _renderRating() {
    return `<div class="rate">
      <h2>Wie war’s?</h2>
      <button type="button" class="first" data-action="rate" data-value="3">Gerne wieder</button>
      <button type="button" data-action="rate" data-value="2">War okay</button>
      <button type="button" data-action="rate" data-value="1">Nie wieder</button>
      <button type="button" data-action="rate" data-value="0">Ohne Bewertung</button>
    </div>`;
  }

  _startTimer(minutes) {
    this._stopTimer();
    this._timer = { step: this._cook.step, endsAt: Date.now() + minutes * 60000, rung: false };
    // Only the digits change: redrawing the page every second would swallow taps.
    this._timerTick = setInterval(() => {
      const timer = this._timer;
      if (!timer) return;
      if (!timer.rung && Date.now() >= timer.endsAt) {
        timer.rung = true;
        this._ring();
        if (this._view === "kochen") this._render();
        return;
      }
      const label = this._timerLabel();
      const time = this._root.querySelector(".timer .time");
      if (time && label) time.textContent = label;
    }, 1000);
    this._render();
  }

  _timerLabel() {
    const left = Math.ceil((this._timer.endsAt - Date.now()) / 1000);
    if (left <= 0) return null;
    return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  }

  _stopTimer() {
    clearInterval(this._timerTick);
    this._timer = null;
  }

  _ring() {
    navigator.vibrate?.([300, 150, 300]);
    try {
      const context = new AudioContext();
      for (const start of [0, 0.4, 0.8]) {
        const tone = context.createOscillator();
        const gain = context.createGain();
        gain.gain.value = 0.25;
        tone.frequency.value = 880;
        tone.connect(gain).connect(context.destination);
        tone.start(context.currentTime + start);
        tone.stop(context.currentTime + start + 0.25);
      }
    } catch {
      // Without sound the timer still shows that the time is up.
    }
  }

  async _keepAwake() {
    try {
      if (!this._wake) this._wake = await navigator.wakeLock?.request("screen");
    } catch {
      // Not available everywhere, for example without HTTPS.
    }
  }

  _releaseWake() {
    this._wake?.release?.().catch(() => {});
    this._wake = null;
  }

  // --- Shopping ---

  _renderShopping() {
    const { stores, shopping } = this._data;
    if (!stores.some((store) => store.id === this._store)) this._store = stores[0]?.id;
    const tabs = stores
      .map((store) => {
        const open = shopping.filter((item) => item.store === store.id && !item.done).length;
        return `<button type="button" data-action="store" data-value="${esc(store.id)}" aria-pressed="${store.id === this._store}">${esc(store.name)} · ${open}</button>`;
      })
      .join("");
    const groups = [];
    for (const item of shopping.filter((entry) => entry.store === this._store)) {
      const title = item.buy_on
        ? `${weekdayName(item.buy_on)} frisch kaufen`
        : `Jetzt kaufen · ${item.section}`;
      let group = groups.find((entry) => entry.title === title);
      if (!group) {
        group = { title, items: [] };
        groups.push(group);
      }
      group.items.push(item);
    }
    const list = groups.length
      ? `<div class="groups">${groups
          .map(
            (group) => `<section class="group"><h2>${esc(group.title)}</h2>
              <ul class="list">${group.items.map((item) => this._renderShoppingItem(item)).join("")}</ul></section>`,
          )
          .join("")}</div>`
      : `<p class="empty" style="flex:1">Nichts zu kaufen. Der Plan füllt diese Liste von selbst, und unten könnt ihr jederzeit etwas ergänzen.</p>`;
    return `<div class="page">
      <h1 class="display">Einkauf</h1>
      <div class="tabs" role="group" aria-label="Laden">${tabs}</div>
      ${
        this._data.adhoc.length
          ? `<div class="adhocbar">${this._data.adhoc
              .map(
                (meal) => `<button type="button" data-action="cook-adhoc" data-value="${esc(meal.id)}">${esc(meal.title)} kochen${icon(ICONS.arrow, 20)}</button>`,
              )
              .join("")}</div>`
          : ""
      }
      ${list}
      <form class="adder" data-form="add-shopping">
        <label class="sr" for="neu">Artikel hinzufügen</label>
        <input id="neu" name="shopping-name" placeholder="Noch etwas dazu…" autocomplete="off" required>
        <button type="submit" aria-label="Hinzufügen">+</button>
      </form>
    </div>`;
  }

  _renderShoppingItem(item) {
    const detail = [
      fmtAmount(item.amount, item.unit),
      item.for.join(", "),
      item.from_stock ? `${fmtAmount(item.from_stock, item.unit)} schon da` : null,
      item.maybe_home ? "Vielleicht noch zu Hause" : null,
    ]
      .filter(Boolean)
      .join(" · ");
    return `<li><button type="button" class="item ${item.done ? "done" : ""}" data-action="tick" data-value="${esc(item.id)}" aria-pressed="${item.done}">
      <span class="box">${item.done ? icon(ICONS.check, 18) : ""}</span>
      <span class="body"><span class="name">${esc(item.name)}</span>${detail ? `<span class="detail">${esc(detail)}</span>` : ""}</span>
      ${item.offer ? `<span class="chip">${esc(item.offer)}</span>` : ""}
    </button></li>`;
  }

  // --- Recipes ---

  _renderRecipes() {
    const { recipes, today } = this._data;
    const query = this._recipeQuery.trim().toLocaleLowerCase("de");
    const hits = recipes.filter(
      (recipe) =>
        !query ||
        recipe.name.toLocaleLowerCase("de").includes(query) ||
        recipe.ingredients.some((item) => item.name.toLocaleLowerCase("de").includes(query)),
    );
    const meta = (recipe) =>
      [
        `${recipe.minutes} Min.`,
        recipe.last_cooked
          ? `zuletzt vor ${Math.max(0, -daysUntil(recipe.last_cooked, today))} Tagen`
          : "noch nie gekocht",
      ].join(" · ");
    const hasStock = this._data.inventory.length > 0;
    const card = (recipe) => {
      let state = "";
      if (hasStock) {
        if (recipe.uses_expiring.length) {
          state = `<span class="state soon">Verbraucht ${esc(recipe.uses_expiring.join(", "))}</span>`;
        }
        state += recipe.missing.length
          ? `<span class="state">Fehlt: ${esc(recipe.missing.join(", "))}</span>`
          : '<span class="state ready">Alles da</span>';
      }
      return `<button type="button" class="recipe" data-action="recipe-open" data-value="${esc(recipe.id)}">
        <span class="name display">${esc(recipe.name)}</span>
        <span class="meta">${esc(meta(recipe))}</span>${state}</button>`;
    };
    const rank = (first, second) =>
      first.missing.length - second.missing.length ||
      second.uses_expiring.length - first.uses_expiring.length ||
      first.name.localeCompare(second.name, "de");
    const grid = (items) => `<div class="recipes">${items.map(card).join("")}</div>`;
    const onlyNow = this._recipeFilter === "now";
    const ready = hits.filter((recipe) => !recipe.missing.length);
    const close = hits.filter((recipe) => recipe.missing.length && recipe.missing.length <= 2);
    let list;
    if (onlyNow && !hasStock) {
      list = `<p class="empty">Noch ist nichts im Vorrat erfasst. Mach eine Inventur oder schick Claude ein Foto vom Kühlschrank, dann steht hier, was ihr daraus kochen könnt.</p>
        <button type="button" class="cta" data-action="audit-start">Inventur starten</button>`;
    } else if (onlyNow) {
      list =
        ready.length || close.length
          ? `${ready.length ? `<h2 class="section-title">Geht sofort</h2>${grid(ready.sort(rank))}` : ""}
             ${close.length ? `<h2 class="section-title">Fehlt nur wenig</h2>${grid(close.sort(rank))}` : ""}`
          : '<p class="empty">Dazu passt gerade kein Rezept. Frag Claude: „Was kann ich aus dem kochen, was da ist?“ Dann kommen auch neue Ideen.</p>';
    } else if (hits.length) {
      list = grid(hasStock ? hits.sort(rank) : hits);
    } else {
      list = `<p class="empty">${recipes.length ? "Dazu gibt es kein Rezept." : "Noch keine Rezepte. Sag Claude zum Beispiel: „Speicher unser Rezept für Flammkuchen.“"}</p>`;
    }
    return `<div class="page">
      <h1 class="display">Worauf habt ihr Lust?</h1>
      <div class="tabs" role="group" aria-label="Auswahl">
        <button type="button" data-action="recipe-filter" data-value="now" aria-pressed="${onlyNow}">Was geht jetzt?</button>
        <button type="button" data-action="recipe-filter" data-value="all" aria-pressed="${!onlyNow}">Alle · ${recipes.length}</button>
      </div>
      <label class="sr" for="suche">Rezept suchen</label>
      <input class="search" id="suche" name="recipe-search" placeholder="Rezept oder Zutat suchen…" autocomplete="off">
      ${list}
    </div>`;
  }

  _renderRecipeSheet() {
    const recipe = this._data.recipes.find((item) => item.id === this._recipe.id);
    if (!recipe) return "";
    const { servings } = this._recipe;
    const factor = servings / recipe.servings;
    let missing = 0;
    const rows = recipe.ingredients.map((item, index) => {
      const amount = item.amount === null ? null : item.amount * factor;
      const stock = recipe.stock[index];
      let state = "Einkaufen";
      let style = "";
      if (item.staple) {
        state = "Vorrat";
        style = "home";
      } else if (stock.optional) {
        state = "Optional";
      } else if (stock.present && (amount === null || stock.have >= amount - 0.001)) {
        state = "Ist da";
        style = "home";
      } else if (stock.maybe) {
        state = "Vielleicht da";
        style = "maybe";
      } else {
        missing += 1;
        if (stock.have > 0) state = `${fmtAmount(stock.have, item.unit)} da`;
      }
      return `<li class="need"><span>${esc(fmtAmount(amount, item.unit))} ${esc(item.name)}</span>
        <span class="state ${style}">${esc(state)}</span></li>`;
    });
    const buttons = missing
      ? `<button type="button" class="main" data-action="recipe-shop">Einkaufen und kochen</button>
         <button type="button" data-action="recipe-cook">Alles da, jetzt kochen</button>`
      : `<button type="button" class="main" data-action="recipe-cook">Jetzt kochen</button>`;
    return `<div class="sheet"><div class="dialog" role="dialog" aria-modal="true" aria-label="${esc(recipe.name)}">
      <h2 class="display">${esc(recipe.name)}</h2>
      ${recipe.summary ? `<p class="note">${esc(recipe.summary)}</p>` : ""}
      <div class="stepper"><span>${servings} ${servings === 1 ? "Portion" : "Portionen"}</span>
        <div>
          <button type="button" data-action="recipe-servings" data-value="-1" aria-label="Weniger Portionen">−</button>
          <button type="button" data-action="recipe-servings" data-value="1" aria-label="Mehr Portionen">+</button>
        </div>
      </div>
      <ul>${rows.join("")}</ul>
      <div class="actions">
        ${buttons}
        <button type="button" data-action="recipe-close">Schließen</button>
      </div>
    </div></div>`;
  }

  // --- Inventory ---

  _renderInventory() {
    const { inventory, locations, expiring, audit, today } = this._data;
    const expiringIds = new Set(expiring.map((item) => item.id));
    const places = locations
      .map((location) => {
        const items = inventory.filter((item) => item.location === location);
        return `<section class="place"><h2 class="display">${esc(location)}</h2>
          ${
            items.length
              ? `<ul>${items
                  .map(
                    (item) => `<li><button type="button" class="stock" data-action="edit" data-value="${esc(item.id)}">
                      <span class="what ${expiringIds.has(item.id) ? "urgent" : ""}">${esc(item.name)}</span>
                      <span class="qty">${esc(fmtAmount(item.amount, item.unit))}</span></button></li>`,
                  )
                  .join("")}</ul>`
              : '<p class="none">Nichts erfasst</p>'
          }</section>`;
      })
      .join("");
    const auditText =
      audit.days_since === null
        ? "Noch keine Inventur gemacht"
        : `Letzte Inventur vor ${audit.days_since} ${audit.days_since === 1 ? "Tag" : "Tagen"}, ${inventory.length} Sachen erfasst`;
    return `<div class="page">
      <header class="row">
        <div><h1 class="display">Was noch da ist</h1><p>${esc(auditText)}</p></div>
        <button type="button" class="ghost" data-action="recipes-now">Was kann ich kochen?</button>
        <button type="button" class="ghost" data-action="edit-new">Hinzufügen</button>
        <button type="button" class="cta" data-action="audit-start">Inventur starten</button>
      </header>
      ${
        expiring.length
          ? `<section class="expiring" aria-label="Läuft bald ab"><strong>Läuft bald ab</strong>${expiring
              .map((item) => `<span>${esc(item.name)}, ${esc(expiryLabel(item.best_before, today))}</span>`)
              .join("")}</section>`
          : ""
      }
      <div class="places">${places}</div>
    </div>`;
  }

  _renderEdit() {
    const edit = this._edit;
    const locations = this._data.locations
      .map((location) => `<option ${location === edit.location ? "selected" : ""}>${esc(location)}</option>`)
      .join("");
    return `<div class="sheet"><form class="dialog" data-form="save-edit" role="dialog" aria-modal="true" aria-label="Vorrat bearbeiten">
      <h2 class="display">${edit.id ? esc(edit.name) : "Neu im Vorrat"}</h2>
      <label class="field">Name<input name="edit-name" value="${esc(edit.name)}" required autocomplete="off"></label>
      <div class="fields">
        <label class="field">Menge<input name="edit-amount" type="number" min="0" step="any" inputmode="decimal" value="${edit.amount ?? ""}"></label>
        <label class="field">Einheit<input name="edit-unit" value="${esc(edit.unit ?? "")}" placeholder="g, ml, Stk." autocomplete="off"></label>
      </div>
      <label class="field">Wo<select name="edit-location">${locations}</select></label>
      <label class="field">Haltbar bis<input name="edit-best" type="date" value="${esc(edit.best_before ?? "")}"></label>
      <div class="actions">
        <button type="submit" class="main">Speichern</button>
        <button type="button" data-action="edit-cancel">Abbrechen</button>
        ${edit.id ? '<button type="button" class="danger" data-action="edit-remove">Aufgebraucht</button>' : ""}
      </div>
    </form></div>`;
  }

  // --- Audit ---

  _renderAudit() {
    const audit = this._audit;
    if (!audit) return this._renderInventory();
    const total = audit.items.length;
    const percent = total ? Math.round((audit.index / total) * 100) : 100;
    const top = `<div class="top"><button type="button" data-action="audit-cancel">Abbrechen</button>
      <span>${total ? `${Math.min(audit.index + 1, total)} von ${total}` : ""}</span></div>
      <div class="bar" aria-hidden="true"><div style="width:${percent}%"></div></div>`;
    if (audit.index >= total) {
      const summary = total
        ? `${total} Sachen geprüft, ${audit.changed} korrigiert, ${audit.removed} ausgetragen.`
        : "Noch ist nichts erfasst. Tragt ein, was da ist, oder schickt Claude ein Foto vom Kühlschrank.";
      return `<div class="audit">${top}
        <section class="card">
          <h1>${total ? "Fertig gezählt" : "Los geht’s"}</h1>
          <p class="sum">${esc(summary)}</p>
          <p class="note">Beim nächsten Plan kommt zuerst dran, was bald abläuft, und nur das Fehlende landet auf der Einkaufsliste.</p>
          <div class="grow"></div>
          <label for="gefunden">Noch etwas gefunden?</label>
          <form data-form="audit-add">
            <input id="gefunden" name="audit-name" placeholder="z. B. Halbe Zitrone" autocomplete="off" required>
            <button type="submit" aria-label="Hinzufügen">+</button>
          </form>
          <button type="button" class="finish" data-action="audit-finish">Inventur abschließen</button>
        </section></div>`;
    }
    const item = audit.items[audit.index];
    const count = audit.count ?? item.amount;
    const best = item.best_before ? `Haltbar bis ${dayLong(item.best_before)}` : "Kein Datum erfasst";
    return `<div class="audit">${top}
      <section class="card">
        <p class="place-name">${esc(item.location)}</p>
        <h1>${esc(item.name)}</h1>
        ${item.amount !== null ? `<p class="last">Zuletzt ${esc(fmtAmount(item.amount, item.unit))}</p>` : ""}
        <p class="best">${esc(best)}</p>
        <div class="grow"></div>
        ${
          item.amount !== null
            ? `<p class="ask">Wie viel ist noch da?</p>
               <div class="counter">
                 <button type="button" data-action="audit-count" data-value="-1" aria-label="Weniger">−</button>
                 <output>${esc(fmtAmount(count, item.unit))}</output>
                 <button type="button" data-action="audit-count" data-value="1" aria-label="Mehr">+</button>
               </div>`
            : '<p class="ask">Ist das noch da?</p>'
        }
      </section>
      <div class="answers">
        <button type="button" class="gone" data-action="audit-gone">Alles weg</button>
        <button type="button" class="ok" data-action="audit-ok">Stimmt so</button>
      </div></div>`;
  }

  // --- Events ---

  _onClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const handler = this[`_on_${target.dataset.action.replace(/-/g, "_")}`];
    handler?.call(this, target.dataset.value);
  }

  _on_noop() {}

  _on_menu() {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  _on_view(view) {
    this._view = view;
    this._swapFrom = null;
    if (view === "kochen") this._keepAwake();
    else this._releaseWake();
    this._render();
  }

  _on_cook(date) {
    const day = this._data.days.find((item) => item.date === date);
    this._cook = { date, step: 0, servings: day?.servings || day?.recipe?.servings || 2, rating: false };
    this._stopTimer();
    this._on_view("kochen");
  }

  _on_cook_adhoc(id) {
    const meal = this._data.adhoc.find((item) => item.id === id);
    if (!meal) return;
    this._cook = { date: null, adhocId: id, step: 0, servings: meal.servings, rating: false };
    this._stopTimer();
    this._on_view("kochen");
  }

  _on_adhoc_remove(id) {
    this._call("remove_adhoc_meal", { id });
  }

  _on_cook_tab(tab) {
    this._cook.tab = tab;
    this._render();
  }

  _on_recipe_filter(filter) {
    this._recipeFilter = filter;
    this._render();
  }

  _on_recipes_now() {
    this._recipeFilter = "now";
    this._on_view("rezepte");
  }

  _on_recipe_open(id) {
    const recipe = this._data.recipes.find((item) => item.id === id);
    if (recipe) {
      this._recipe = { id, servings: recipe.servings };
      this._render();
    }
  }

  _on_recipe_close() {
    this._recipe = null;
    this._render();
  }

  _on_recipe_servings(delta) {
    this._recipe.servings = Math.max(1, this._recipe.servings + Number(delta));
    this._render();
  }

  async _on_recipe_shop() {
    const { id, servings } = this._recipe;
    this._recipe = null;
    if (await this._call("add_adhoc_meal", { recipe_id: id, servings })) {
      this._on_view("einkauf");
    } else {
      this._render();
    }
  }

  async _on_recipe_cook() {
    const { id, servings } = this._recipe;
    this._recipe = null;
    const meal = await this._call("add_adhoc_meal", { recipe_id: id, servings, shop: false });
    if (meal) {
      this._cook = { date: null, adhocId: meal.id, step: 0, servings, rating: false };
      this._stopTimer();
      this._on_view("kochen");
    } else {
      this._render();
    }
  }

  _on_servings(delta) {
    this._cook.servings = Math.max(1, this._cook.servings + Number(delta));
    this._render();
  }

  _on_step(delta) {
    this._cook.step = Math.max(0, this._cook.step + Number(delta));
    this._render();
  }

  _on_cook_finish() {
    this._stopTimer();
    this._cook.rating = true;
    this._render();
  }

  async _on_rate(rating) {
    const { adhocId, date, servings } = this._cook;
    const args = adhocId ? { id: adhocId, servings } : { date, servings };
    if (Number(rating)) args.rating = Number(rating);
    if (await this._call(adhocId ? "mark_adhoc_cooked" : "mark_cooked", args)) {
      this._cook = null;
      this._on_view("woche");
    }
  }

  _on_done_plain(date) {
    this._call("mark_cooked", { date });
  }

  _on_timer_start(minutes) {
    this._startTimer(Number(minutes));
  }

  _on_timer_stop() {
    this._stopTimer();
    this._render();
  }

  _on_swap_start(date) {
    this._swapFrom = date;
    this._render();
  }

  _on_swap_cancel() {
    this._swapFrom = null;
    this._render();
  }

  async _on_swap_to(date) {
    const first = this._swapFrom;
    this._swapFrom = null;
    if (first && first !== date) await this._call("swap_days", { first, second: date });
    this._render();
  }

  _on_store(store) {
    this._store = store;
    this._render();
  }

  _on_tick(id) {
    const item = this._data.shopping.find((entry) => entry.id === id);
    if (!item) return;
    item.done = !item.done;
    this._render();
    this._call("set_shopping_item_done", { id, done: item.done });
  }

  _on_edit(id) {
    const item = this._data.inventory.find((entry) => entry.id === id);
    if (item) {
      this._edit = { ...item };
      this._render();
    }
  }

  _on_edit_new() {
    this._edit = { id: null, name: "", amount: null, unit: "", location: this._data.locations[0], best_before: null };
    this._render();
  }

  _on_edit_cancel() {
    this._edit = null;
    this._render();
  }

  async _on_edit_remove() {
    const { id } = this._edit;
    this._edit = null;
    await this._call("update_inventory", { items: [{ id, remove: true }] });
    this._render();
  }

  _on_audit_start() {
    const order = this._data.locations;
    const items = [...this._data.inventory].sort(
      (first, second) =>
        order.indexOf(first.location) - order.indexOf(second.location) ||
        first.name.localeCompare(second.name, "de"),
    );
    this._audit = { items, index: 0, count: null, changed: 0, removed: 0 };
    this._view = "inventur";
    this._render();
  }

  _on_audit_cancel() {
    this._audit = null;
    this._view = "kuehlschrank";
    this._render();
  }

  _on_audit_count(direction) {
    const audit = this._audit;
    const item = audit.items[audit.index];
    const count = audit.count ?? item.amount;
    const step = stepSize(count, item.unit);
    audit.count = Math.max(0, Math.round((count + Number(direction) * step) * 100) / 100);
    this._render();
  }

  _on_audit_ok() {
    const audit = this._audit;
    const item = audit.items[audit.index];
    if (audit.count !== null && audit.count !== item.amount) {
      if (audit.count === 0) audit.removed += 1;
      else audit.changed += 1;
      this._call("update_inventory", {
        items: [{ id: item.id, amount: audit.count, unit: item.unit }],
      });
    }
    audit.index += 1;
    audit.count = null;
    this._render();
  }

  _on_audit_gone() {
    const audit = this._audit;
    const item = audit.items[audit.index];
    audit.removed += 1;
    audit.index += 1;
    audit.count = null;
    this._call("update_inventory", { items: [{ id: item.id, remove: true }] });
    this._render();
  }

  async _on_audit_finish() {
    if (await this._call("record_inventory_audit", {})) this._on_audit_cancel();
  }

  async _onSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const fields = Object.fromEntries(new FormData(form));
    switch (form.dataset.form) {
      case "add-shopping":
        form.reset();
        await this._call("add_shopping_items", {
          items: [{ name: fields["shopping-name"].trim(), store: this._store }],
        });
        break;
      case "audit-add":
        form.reset();
        await this._call("update_inventory", {
          items: [{ name: fields["audit-name"].trim() }],
        });
        break;
      case "save-edit": {
        const change = {
          name: fields["edit-name"].trim(),
          location: fields["edit-location"],
          amount: fields["edit-amount"] === "" ? null : Number(fields["edit-amount"]),
          unit: fields["edit-unit"].trim() || null,
          best_before: fields["edit-best"] || null,
        };
        if (this._edit.id) change.id = this._edit.id;
        this._edit = null;
        await this._call("update_inventory", { items: [change] });
        this._render();
        break;
      }
      default:
    }
  }
}

customElements.define("kuechenplan-panel", KuechenplanPanel);
