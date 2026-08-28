import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import Department, Equipment, Room, Section, User, db


def main():
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        director = User(username="proviseur.test", role="directeur", full_name="Proviseur Test", must_change_password=False)
        director.set_password("Lyttib")
        section = Section(name="Section Technique", code="STT")
        db.session.add_all([director, section])
        db.session.flush()
        department = Department(name="Électrotechnique", code="GEL", section_id=section.id)
        db.session.add(department)
        db.session.commit()
        department_id = department.id

    with app.test_client() as client:
        login = client.post("/login", data={"username": "proviseur.test", "password": "Lyttib"})
        assert login.status_code == 302
        created = client.post("/salles/nouvelle", data={
            "name": "Atelier Électrotechnique", "type": "Atelier", "capacity": "28",
            "location": "Bâtiment technique", "department_id": str(department_id),
        })
        assert created.status_code == 302
        with app.app_context():
            room = Room.query.filter_by(name="Atelier Électrotechnique").one()
            assert room.capacity == 28
            assert room.department_id == department_id
            room_id = room.id
        equipment = client.post(f"/salles/{room_id}/equipement", data={
            "name": "Vidéoprojecteur", "quantity": "2", "status": "Opérationnel",
        })
        assert equipment.status_code == 302
        with app.app_context():
            item = Equipment.query.filter_by(name="Vidéoprojecteur", room_id=room_id).one()
            assert item.quantity == 2
        edited = client.post(f"/salles/{room_id}/modifier", data={
            "name": "Atelier GEL 1", "type": "Atelier", "capacity": "30", "location": "Bâtiment B",
        })
        assert edited.status_code == 302
        with app.app_context():
            assert Room.query.get(room_id).name == "Atelier GEL 1"
        deleted = client.get(f"/salles/{room_id}/supprimer")
        assert deleted.status_code == 302
        with app.app_context():
            assert Room.query.get(room_id) is None
        invalid = client.post("/salles/nouvelle", data={"name": "", "type": "Salle", "capacity": "40"})
        assert invalid.status_code == 302
    print("ROOM_MANAGEMENT_FEATURE_TEST_OK")


if __name__ == "__main__":
    main()
