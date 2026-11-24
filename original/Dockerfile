FROM skills-1c:lab5
COPY src/ /lab3/src/
COPY config.json check.py /lab3/
ENV PYTHONPATH=/lab3/src:/app
ENTRYPOINT ["python", "/lab3/check.py"]
