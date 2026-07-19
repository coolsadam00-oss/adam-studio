const teamToggle = document.querySelector("#teamToggle");
const extraTeam = document.querySelector("#extraTeam");

if (teamToggle && extraTeam) {
  teamToggle.addEventListener("click", () => {
    const willOpen = extraTeam.hidden;
    extraTeam.hidden = !willOpen;
    teamToggle.setAttribute("aria-expanded", String(willOpen));
    teamToggle.textContent = willOpen ? "Show less" : "View more";

    if (!willOpen) {
      extraTeam.querySelectorAll("details[open]").forEach((member) => {
        member.open = false;
      });
      document.querySelector("#team")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  });
}
