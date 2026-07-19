import unittest

import adam_studio_app


class TeamSectionTests(unittest.TestCase):
    def test_team_roles_are_inside_clickable_name_details(self):
        response = adam_studio_app.app.test_client().get("/")
        html = response.get_data(as_text=True)
        team_html = html.split('<section id="team"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(team_html.count('<details class="team-member">'), 6)
        self.assertIn("<summary>Adam Cools</summary>", team_html)
        self.assertIn("<summary>Emir Yilmaz</summary>", team_html)
        self.assertIn("<summary>Nura Akar</summary>", team_html)
        self.assertEqual(team_html.count('class="team-role"'), 203)

    def test_team_shows_six_members_before_view_more(self):
        response = adam_studio_app.app.test_client().get("/")
        html = response.get_data(as_text=True)
        team_html = html.split('<section id="team"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(team_html.count('class="team-member"'), 6)
        self.assertEqual(team_html.count('class="team-member team-extra"'), 197)
        self.assertIn("<summary>Liam Vermeulen</summary>", team_html)
        self.assertIn("<summary>Avery Collins</summary>", team_html)
        self.assertIn(
            'id="teamToggle" aria-expanded="false" aria-controls="extraTeam"',
            team_html,
        )

    def test_every_team_member_has_a_role_description(self):
        self.assertEqual(len(adam_studio_app.TEAM_MEMBERS), 203)
        self.assertTrue(
            all(member["description"] for member in adam_studio_app.TEAM_MEMBERS)
        )

        response = adam_studio_app.app.test_client().get("/")
        html = response.get_data(as_text=True)
        self.assertIn(
            "Building gameplay systems and interactive features with code.",
            html,
        )


if __name__ == "__main__":
    unittest.main()
