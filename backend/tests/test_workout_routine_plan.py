"""Regressoes PostgreSQL da previa e aplicacao de ciclos de treino."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.deps import get_current_user, get_session
from app.main import app
from app.models import (
    Equipment,
    Exercise,
    ExerciseKind,
    ExerciseLevel,
    ExerciseTranslation,
    MuscleGroup,
    Routine,
    RoutineExercise,
    User,
    WorkoutRoutineReceipt,
)
from app.schemas import RoutinePlanIn
from app.routers.workout import _allowed_levels, _select_generation_exercise, _equipment_options
from app.routers import workout as workout_router
from app.services.coaching import routine_variation


class WorkoutRoutinePlanTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.user = User(email=f"routine-plan-{uuid4()}@example.invalid", password_hash="test-only")
        self.session.add(self.user)
        self.session.flush()
        self.exercise = self.exercise_record(
            "routine-plan-press", MuscleGroup.chest, Equipment.dumbbell, ExerciseLevel.beginner
        )
        self.session.flush()
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.session.close()
        self.transaction.rollback()
        self.connection.close()

    def exercise_record(
        self, slug: str, group: MuscleGroup, equipment: Equipment, level: ExerciseLevel
    ) -> Exercise:
        exercise = Exercise(
            slug=f"{slug}-{uuid4().hex[:8]}",
            muscle_group=group,
            equipment=equipment,
            kind=ExerciseKind.strength,
            level=level,
            user_id=self.user.id,
        )
        self.session.add(exercise)
        self.session.flush()
        self.session.add(
            ExerciseTranslation(exercise_id=exercise.id, locale="pt-BR", name="Supino teste")
        )
        self.session.flush()
        return exercise

    def draft(self, name: str = "Treino teste") -> dict:
        return {
            "name": name,
            "items": [
                {
                    "exercise_id": self.exercise.id,
                    "target_sets": 3,
                    "target_reps": 10,
                    "target_weight_kg": None,
                    "target_duration_min": None,
                    "rest_seconds": 90,
                }
            ],
        }

    def apply(self, key: str, **overrides) -> dict:
        payload = {
            "operation_key": key,
            "destination": "append",
            "routines": [self.draft()],
        }
        payload.update(overrides)
        return self.client.post("/me/routines/apply", json=payload)

    def test_plan_accepts_bulk_renewal_for_more_than_five_routines(self):
        plan = RoutinePlanIn.model_validate(
            {
                "operation_key": str(uuid4()),
                "destination": "append",
                "routines": [self.draft(f"Treino {index}") for index in range(6)],
            }
        )

        self.assertEqual(len(plan.routines), 6)

    def test_variation_reserves_a_compatible_exercise_used_by_a_later_slot(self):
        first_exercise = self.exercise_record(
            "variation-first", MuscleGroup.chest, Equipment.dumbbell, ExerciseLevel.beginner
        )
        second_exercise = self.exercise_record(
            "variation-second", MuscleGroup.chest, Equipment.machine, ExerciseLevel.beginner
        )
        routine = Routine(user_id=self.user.id, name="Rotina", position=0)
        self.session.add(routine)
        self.session.flush()
        routine.items.extend(
            [
                RoutineExercise(routine_id=routine.id, exercise_id=first_exercise.id, position=0),
                RoutineExercise(routine_id=routine.id, exercise_id=second_exercise.id, position=1),
            ]
        )
        self.session.flush()

        def prefer_later_exercise(candidates):
            return next(
                (candidate for candidate in candidates if candidate.id == second_exercise.id),
                candidates[0],
            )

        original_exec = self.session.exec
        candidate_queries = 0

        def execute_with_only_later_candidate(statement, *args, **kwargs):
            nonlocal candidate_queries
            entity = statement.column_descriptions[0].get("entity")
            if entity is Exercise:
                candidate_queries += 1
                candidates = [second_exercise] if candidate_queries == 1 else []
                return SimpleNamespace(all=lambda: candidates)
            return original_exec(statement, *args, **kwargs)

        with (
            patch.object(self.session, "exec", side_effect=execute_with_only_later_candidate),
            patch("app.services.coaching.random.choice", side_effect=prefer_later_exercise),
        ):
            variation = routine_variation(
                self.session,
                routine,
                "pt-BR",
                {ExerciseLevel.beginner},
                {Equipment.machine},
            )

        selected_ids = [item.new_exercise.id for item in variation.items]
        self.assertNotEqual(selected_ids[0], second_exercise.id)
        self.assertEqual(selected_ids[1], second_exercise.id)
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertFalse(variation.items[0].matches_preferences)
        self.assertTrue(variation.items[1].matches_preferences)

    def test_repeated_apply_returns_the_same_routine_without_creating_another(self):
        key = str(uuid4())
        first = self.apply(key)
        self.assertEqual(first.status_code, 200, first.text)
        first_routine_id = first.json()["routines"][0]["id"]

        retry = self.apply(key)

        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json()["routines"][0]["id"], first_routine_id)
        self.assertEqual(
            len(self.session.exec(select(Routine).where(Routine.user_id == self.user.id)).all()), 1
        )
        self.assertEqual(
            len(
                self.session.exec(
                    select(WorkoutRoutineReceipt).where(
                        WorkoutRoutineReceipt.user_id == self.user.id
                    )
                ).all()
            ),
            1,
        )

    def test_reusing_an_operation_key_for_changed_content_is_rejected(self):
        key = str(uuid4())
        self.assertEqual(self.apply(key).status_code, 200)
        changed = self.draft("Outro nome")

        response = self.apply(key, routines=[changed])

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "ROUTINE_OPERATION_KEY_REUSED")

    def test_replace_archives_all_active_sources_in_the_same_apply(self):
        original = self.apply(str(uuid4())).json()["routines"][0]

        response = self.apply(
            str(uuid4()),
            destination="replace",
            expected_active_ids=[original["id"]],
            expected_sources={str(original["id"]): original["revision"]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["archived_ids"], [original["id"]])
        active = self.client.get("/me/routines").json()
        archived = self.client.get("/me/routines?include_archived=true").json()
        self.assertEqual(len(active), 1)
        self.assertNotEqual(active[0]["id"], original["id"])
        self.assertTrue(next(routine for routine in archived if routine["id"] == original["id"])["archived_at"])

    def test_stale_source_is_rejected_before_archiving_or_creating(self):
        original = self.apply(str(uuid4())).json()["routines"][0]
        changed_draft = self.draft("Nome atualizado")
        changed_draft["items"][0]["target_reps"] = 12
        update = self.client.put(
            f"/me/routines/{original['id']}", json=changed_draft
        )
        self.assertEqual(update.status_code, 200, update.text)

        response = self.apply(
            str(uuid4()),
            archive_ids=[original["id"]],
            expected_sources={str(original["id"]): original["revision"]},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "ROUTINE_PLAN_STALE")
        self.assertEqual(len(self.client.get("/me/routines").json()), 1)

    def test_stale_copy_source_is_rejected_even_when_original_would_be_kept(self):
        original = self.apply(str(uuid4())).json()["routines"][0]
        changed_draft = self.draft("Fonte editada")
        changed_draft["items"][0]["target_reps"] = 12
        self.assertEqual(
            self.client.put(f"/me/routines/{original['id']}", json=changed_draft).status_code,
            200,
        )

        response = self.apply(
            str(uuid4()),
            routines=[self.draft("Copia")],
            source_ids=[original["id"]],
            expected_sources={str(original["id"]): original["revision"]},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "ROUTINE_PLAN_STALE")
        self.assertEqual(len(self.client.get("/me/routines").json()), 1)

    def test_level_and_equipment_constraints_use_ceiling_and_mixed_families(self):
        advanced_barbell = self.exercise_record(
            "routine-plan-expert", MuscleGroup.chest, Equipment.barbell, ExerciseLevel.expert
        )
        beginner_machine = self.exercise_record(
            "routine-plan-machine", MuscleGroup.chest, Equipment.machine, ExerciseLevel.beginner
        )
        self.session.flush()

        selected = _select_generation_exercise(
            self.session,
            self.user,
            advanced_barbell,
            set(),
            _allowed_levels("beginner"),
            _equipment_options("free_weights"),
        )

        self.assertNotEqual(selected.id, advanced_barbell.id)
        self.assertIn(selected.level, _allowed_levels("beginner"))
        self.assertIn(selected.equipment, _equipment_options("free_weights"))
        self.assertNotIn(ExerciseLevel.expert, _allowed_levels("intermediate"))
        self.assertIn(ExerciseLevel.expert, _allowed_levels("advanced"))
        self.assertIn(Equipment.machine, _equipment_options("mixed"))
        self.assertNotIn(Equipment.machine, _equipment_options("free_weights"))
        self.assertNotEqual(beginner_machine.id, selected.id)

    def test_generated_preview_slots_are_required_and_preferences_are_server_checked(self):
        template_exercise = Exercise(
            slug=f"routine-plan-template-{uuid4().hex[:8]}",
            muscle_group=MuscleGroup.chest,
            equipment=Equipment.dumbbell,
            kind=ExerciseKind.strength,
            level=ExerciseLevel.beginner,
        )
        self.session.add(template_exercise)
        self.session.flush()
        self.session.add(
            ExerciseTranslation(
                exercise_id=template_exercise.id,
                locale="pt-BR",
                name="Supino de modelo",
            )
        )
        self.session.flush()
        with patch.object(
            workout_router,
            "TEMPLATES",
            {2: [("Treino gerado", [template_exercise.slug])]},
        ):
            preview = self.client.post(
                "/me/routines/preview",
                json={"frequency": 2, "level": "beginner", "equipment_mode": "free_weights"},
            )
            self.assertEqual(preview.status_code, 200, preview.text)
            preview_item = preview.json()["routines"][0]["items"][0]
            valid_plan = {
                "operation_key": str(uuid4()),
                "destination": "append",
                "generation": {
                    "frequency": 2,
                    "level": "beginner",
                    "equipment_mode": "free_weights",
                },
                "routines": [
                    {
                        "name": "Treino aceito",
                        "items": [
                            {
                                "exercise_id": preview_item["exercise"]["id"],
                                "slot_id": preview_item["slot_id"],
                                "target_sets": 3,
                                "target_reps": 10,
                                "rest_seconds": 90,
                            }
                        ],
                    }
                ],
            }
            missing_slot = {
                **valid_plan,
                "operation_key": str(uuid4()),
                "routines": [
                    {
                        "name": "Vaga sem identidade",
                        "items": [{**valid_plan["routines"][0]["items"][0], "slot_id": None}],
                    }
                ],
            }
            self.assertEqual(
                self.client.post("/me/routines/apply", json=missing_slot).json()["detail"],
                "ROUTINE_GENERATION_COVERAGE",
            )

            valid = self.client.post("/me/routines/apply", json=valid_plan)
            self.assertEqual(valid.status_code, 200, valid.text)

            wrong_exercise = self.exercise_record(
                "routine-plan-wrong-group",
                MuscleGroup.back,
                Equipment.dumbbell,
                ExerciseLevel.beginner,
            )
            self.session.flush()
            mismatched_slot = {
                **valid_plan,
                "operation_key": str(uuid4()),
                "routines": [
                    {
                        "name": "Treino fora do grupo",
                        "items": [
                            {
                                "exercise_id": wrong_exercise.id,
                                "slot_id": preview_item["slot_id"],
                                "target_sets": 3,
                                "target_reps": 10,
                                "rest_seconds": 90,
                            }
                        ],
                    }
                ],
            }
            response = self.client.post("/me/routines/apply", json=mismatched_slot)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], "ROUTINE_SLOT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
