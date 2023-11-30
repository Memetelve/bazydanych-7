from flask import Flask, jsonify, request
from neo4j import AsyncGraphDatabase

app = Flask(__name__)

uri = "neo4j://127.0.0.1:7687"


async def get_driver():
    return AsyncGraphDatabase.driver(uri, auth=("neo4j", "test1234"))


def serialize_employee(employee):
    return {
        "name": employee[0]["name"],
        "surname": employee[0]["surname"],
        "employee_id": employee[0]["employee_id"],
        "department": employee[1]["dept_name"],
    }


def serialize_department(department):
    return {
        "name": department[0]["dept_name"],
    }


def create_filter_string(params, args):
    filtering_string = "{"
    not_first_param = False
    for param in params:
        if param in args:
            if not_first_param:
                filtering_string += ", "
            if param == "employee_id":
                filtering_string += f"{param}: {args[param]}"
            else:
                filtering_string += f"{param}: '{args[param]}'"
            not_first_param = True

    filtering_string += "}"
    return filtering_string


@app.route("/api/employees/", methods=["GET"])
async def get_employees():
    driver = await get_driver()
    args = request.args.to_dict()

    params_employee = ["name", "surname", "employee_id"]
    filtering_string_employee = create_filter_string(params_employee, args)

    params_dept = ["dept_name"]
    filtering_string_dept = create_filter_string(params_dept, args)

    async with driver.session() as session:
        employee = await session.run(
            f"MATCH (e:Employee {filtering_string_employee})-[:WORKS_IN|MANAGES]->(d:Department {filtering_string_dept}) RETURN e, d"
        )
        employee = await employee.values()

    employees = [serialize_employee(employee) for employee in employee]

    return jsonify(employees)


@app.route("/api/employees/", methods=["POST"])
async def add_employee():
    driver = await get_driver()
    args = request.args.to_dict()

    check_params = ["name", "surname", "employee_id", "dept_name"]
    for param in check_params:
        if param not in args:
            return jsonify({"message": f"missing {param}"}), 400

    # check if employee name + surname already exists
    params_employee = ["name", "surname"]
    filtering_string_employee = create_filter_string(params_employee, args)

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (e:Employee {filtering_string_employee}) RETURN e"
        )
        result = await result.values()

        if len(result) > 0:
            return jsonify({"message": "Employee already exists"}), 400

        # add employee
        params_employee = ["name", "surname", "employee_id"]
        filtering_string_employee = create_filter_string(params_employee, args)

        params_dept = ["dept_name"]
        filtering_string_dept = create_filter_string(params_dept, args)

        result = await session.run(
            f"CREATE (e:Employee {filtering_string_employee}) RETURN e"
        )
        # create relationship
        result = await session.run(
            f"MATCH (e:Employee {filtering_string_employee}) MATCH (d:Department {filtering_string_dept}) CREATE (e)-[:WORKS_IN]->(d)"
        )

        result = await result.values()

    return jsonify({"message": "Employee added successfully"}), 301


@app.route("/api/employees/<employee_id>", methods=["PUT"])
async def update_employee(employee_id):
    driver = await get_driver()
    args = request.args.to_dict()

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}}) RETURN e"
        )
        result = await result.values()

        if len(result) == 0:
            return jsonify({"message": "Employee does not exist"}), 400

        # update employee
        params_employee = ["name", "surname"]
        filtering_string_employee = create_filter_string(params_employee, args)

        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}}) SET e {filtering_string_employee} RETURN e"
        )
        result = await result.values()

        # update department
        params_dept = ["dept_name"]
        filtering_string_dept = create_filter_string(params_dept, args)

        # delete last relationship
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}})-[r:WORKS_IN]->(d:Department) DELETE r"
        )

        # create new relationship
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}}) MATCH (d:Department {filtering_string_dept}) CREATE (e)-[:WORKS_IN]->(d)"
        )

    return jsonify({"message": "Employee updated successfully"}), 301


@app.route("/api/employees/<employee_id>", methods=["DELETE"])
async def delete_employee(employee_id):
    driver = await get_driver()

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}}) RETURN e"
        )
        result = await result.values()

        if len(result) == 0:
            return jsonify({"message": "Employee does not exist"}), 400

        # get all employees working in the same department
        employees = await session.run(
            f"MATCH (e:Employee)-[:WORKS_IN]->(d:Department)<-[:WORKS_IN]-(e2:Employee) WHERE e.employee_id = '{employee_id}' RETURN e2"
        )
        employees = await result.values()

        # delete employee
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}}) DETACH DELETE e"
        )

        # if there are no more employees working in the same department, delete the department
        if len(employees) == 1:
            result = await session.run(
                f"MATCH (e:Employee {{employee_id: '{employee_id}'}})-[r:WORKS_IN]->(d:Department) DELETE r"
            )
            result = await session.run(
                "MATCH (d:Department) WHERE NOT (d)<-[:WORKS_IN]-() DELETE d"
            )
        else:
            # if there are more employees working in the same department, update the department manager to the first employee [:MANAGES] relationship
            # delete last relationship
            result = await session.run(
                f"MATCH (e:Employee {{employee_id: '{employee_id}'}})-[r:WORKS_IN]->(d:Department) DELETE r"
            )
            # create new relationship
            result = await session.run(
                f"MATCH (e:Employee {{employee_id: '{employees[1]['employee_id']}'}}) MATCH (d:Department {{dept_name: '{employees[1]['dept_name']}'}}) CREATE (e)-[:MANAGES]->(d)"
            )

    return jsonify({"message": "Employee deleted successfully"}), 301


@app.route("/api/employees/:employye_id/subordinates", methods=["GET"])
async def get_subordinates(employee_id):
    driver = await get_driver()

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (e:Employee {{employee_id: '{employee_id}'}})-[:MANAGES]->(d:Department)<-[:WORKS_IN]-(e2:Employee) RETURN e2"
        )
        result = await result.values()

    employees = [serialize_employee(employee) for employee in result]

    return jsonify(employees)


@app.route("/api/departments", methods=["GET"])
async def get_departments():
    driver = await get_driver()

    async with driver.session() as session:
        result = await session.run("MATCH (d:Department) RETURN d")
        result = await result.values()

    departments = [serialize_department(department) for department in result]

    return jsonify(departments)


@app.route("/api/departments/<dept_name>/employees", methods=["GET"])
async def get_departments_employees(dept_name):
    driver = await get_driver()

    async with driver.session() as session:
        result = await session.run(
            f"MATCH (e:Employee)-[:WORKS_IN]->(d:Department {{dept_name: '{dept_name}'}}) RETURN e, d"
        )
        result = await result.values()

    employees = [serialize_employee(employee) for employee in result]

    return jsonify(employees)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
