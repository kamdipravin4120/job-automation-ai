from __future__ import annotations
import logging
from src.models import CandidateProfile, JobPosting, TailoredResumeBundle, ExperienceItem, EducationItem, ProjectItem

class StaticResumeGenerator:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger.getChild("static_generator")

    def generate(self, profile: CandidateProfile, job: JobPosting) -> TailoredResumeBundle:
        self.logger.info("Generating static resume bundle for %s", job.job_id)
        
        # Simple generic cover letter
        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job.title} position at {job.company}. With my background as a {profile.headline}, I am confident that my skills in {', '.join(profile.skills[:5])} make me a great fit for your team.

At my previous role at {profile.experience[0].company if profile.experience else 'various companies'}, I focused on building robust systems and improving operational efficiency. I am excited about the opportunity to bring my expertise in {profile.skills[0]} and {profile.skills[1]} to {job.company}.

Thank you for your time and consideration.

Best regards,
{profile.name}"""

        # Simple generic recruiter pitch
        pitch = f"Hi, I'm {profile.name}, a {profile.headline}. I saw the {job.title} opening at {job.company} and wanted to reach out. I have extensive experience in {', '.join(profile.skills[:3])} and have previously worked on similar challenges. I'd love to discuss how my background can help your team."

        return TailoredResumeBundle(
            job_id=job.job_id,
            source=job.source,
            headline=profile.headline,
            summary=profile.summary,
            skills=profile.skills,
            experience=profile.experience,
            education=profile.education,
            projects=profile.projects,
            certifications=profile.certifications,
            resume_text=profile.as_embedding_text(),
            recruiter_pitch=pitch,
            cover_letter=cover_letter
        )
