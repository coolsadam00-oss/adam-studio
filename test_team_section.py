import unittest

import adam_studio_app


class TeamSectionTests(unittest.TestCase):
    def test_team_roles_are_inside_clickable_name_details(self):
        response = adam_studio_app.app.test_client().get("/")
        html = response.get_data(as_text=True)
        team_html = html.split('<section id="team"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(team_html.count('<details class="team-member">'), 3)
        self.assertIn("<summary>Adam Cools</summary>", team_html)
        self.assertIn("<summary>Emir Yilmaz</summary>", team_html)
        self.assertIn("<summary>Nura Akar</summary>", team_html)
        self.assertEqual(team_html.count('class="team-role"'), 3)


if __name__ == "__main__":
    unittest.main()
