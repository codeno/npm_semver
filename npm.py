
DIGITS = '0123456789'
WILDCARD = "xX*"

"""################ version ################"""


class VersionPart:
    def __init__(self, terminator: str = ".") -> None:
        self.value = ""

        self.__terminator__ = terminator

    def accept(self, char: str) -> int:
        if char in self.__terminator__:
            self.validate()
            return 1

        if not self.is_valid(char):
            raise ValueError("Invalid version.")

        self.value += char
        return 0

    def is_valid(self, char: str) -> bool:
        pass

    def validate(self) -> None:
        if self.value == "":
            raise ValueError("Invalid version.")

    def compare(self, part: "VersionPart") -> int:
        return 0


class Prefix(VersionPart):
    def __init__(self) -> None:
        super().__init__(DIGITS + WILDCARD)

    def accept(self, char: str) -> int:
        return -super().accept(char)

    def is_valid(self, char: str) -> bool:
        return self.value == "" and char in "v="

    def validate(self) -> None:
        pass


class Numeric(VersionPart):
    def __init__(self, is_in_expression: bool = False) -> None:
        super().__init__()

        self.__is_in_expression__ = is_in_expression

    def is_valid(self, char: str) -> bool:
        result = char.isdigit()

        if self.__is_in_expression__ and self.value == "":
            result = result or char in WILDCARD

        return result and (self.value == "" or self.value not in "0" + (WILDCARD if self.__is_in_expression__ else ""))

    def compare(self, numeric: "Numeric") -> int:
        return 0 if numeric.value in WILDCARD else int(self.value) - int(numeric.value)


class Patch(Numeric):
    def __init__(self, is_in_expression: bool = False) -> None:
        super().__init__(is_in_expression)
        VersionPart.__init__(self, "-+")

    def accept(self, char: str) -> int:
        result = super().accept(char)

        if result == 1 and char == '+':
            result = 2

        return result


class Prerelease(VersionPart):
    def __init__(self) -> None:
        super().__init__("+")

        self.parts: list[str] = []

        self.__invalid_numeric__ = False

    def accept(self, char: str) -> int:
        result = super().accept(char)

        if (result == 1 or char == '.') and (len(self.parts) == 0 or self.parts[-1] == "" or self.__invalid_numeric__):
            raise ValueError("Invalid version.")
        if result == 0:
            if char == '.':
                self.parts.append("")
            else:
                if len(self.parts) == 0:
                    self.parts.append("")
                self.__invalid_numeric__ = (self.__invalid_numeric__ or self.parts[-1] == "0") and char.isdigit()
                self.parts[-1] += char

        return result

    def is_valid(self, char: str) -> bool:
        return char.isalnum() or char in "-."

    def compare(self, prerelease: "Prerelease") -> int:
        if self.value == prerelease.value:
            return 0

        if self.value == "":
            return 1

        if prerelease.value == "":
            return -1

        for i in range(min(len(self.parts), len(prerelease.parts))):
            if self.parts[i] != prerelease.parts[i]:
                if self.parts[i].isdigit() and prerelease.parts[i].isdigit():
                    return -1 if not prerelease.parts[i].isdigit() else int(self.parts[i]) - int(prerelease.parts[i])
                return 1 if prerelease.parts[i].isdigit() or self.parts[i] > prerelease.parts[i] else -1
        return len(self.parts) - len(prerelease.parts)


class Build(VersionPart):
    def __init__(self) -> None:
        super().__init__()

        VersionPart.__init__(self, "")

    def is_valid(self, char: str) -> bool:
        return True


class Version:
    def __init__(self, version: str = None, is_in_expression: bool = False) -> None:
        self.value = ""
        self.prefix = Prefix()
        self.major = Numeric(is_in_expression)
        self.minor = Numeric(is_in_expression)
        self.patch = Patch(is_in_expression)
        self.prerelease = Prerelease()
        self.build = Build()
        self.parts = [self.prefix, self.major, self.minor, self.patch, self.prerelease, self.build]
        self.is_in_expression = is_in_expression

        self.__is_valid__ = None
        self.__current__ = 0
        if not is_in_expression or version is not None:
            self.__parse__(version)

    def __parse__(self, version: str) -> None:
        if version is None or version == "":
            raise ValueError("Invalid version.")

        for char in version:
            self.accept(char)

        self.construct()

    def construct(self) -> None:
        if self.__is_valid__ is not None:
            raise RuntimeError("Version already built.")

        try:
            self.parts[self.__current__].validate()
            if not self.is_in_expression and self.__current__ < 2:
                raise ValueError("Invalid version.")
        except ValueError as e:
            self.__is_valid__ = False
            raise e

        self.__is_valid__ = True

    def accept(self, char: str) -> None:
        if self.__is_valid__ is not None:
            raise RuntimeError("Version already built.")

        step = self.parts[self.__current__].accept(char)
        self.__current__ += abs(step)
        if step < 0:
            self.parts[self.__current__].accept(char)

        self.value += char

    def compare(self, version: "Version", include_prerelease: bool = False) -> "int | None":
        result = 0

        for i in range(1, 4):
            result = self.parts[i].compare(version.parts[i])
            if result != 0 or version.parts[i].value in WILDCARD:
                break

        if not include_prerelease and self.prerelease.value != "" and (result != 0 or version.prerelease.value == ""):
            return None

        if result == 0 and (include_prerelease or version.prerelease.value != ""):
            result = self.prerelease.compare(version.prerelease)

        return result

    def __str__(self) -> str:
        return self.value


"""################ version expression ################"""


class ConditionPart:
    def __init__(self) -> None:
        self.value = ""

        self.__can_accept_space__ = False

    def accept(self, char: str) -> int:
        pass

    def construct(self) -> None:
        pass


class Comparator(ConditionPart):
    def __init__(self, char: str) -> None:
        super().__init__()

        if char not in "<>=":
            raise ValueError("Invalid comparator.")

        self.value = char

    def accept(self, char: str) -> int:
        if char == '=' and self.value in "<>":
            self.value += char
            return 1
        return -2


class Space(ConditionPart):
    def __init__(self, is_mandatory: bool = False) -> None:
        super().__init__()

        self.is_mandatory = is_mandatory

        self.__can_accept_space__ = True

    def accept(self, char: str) -> int:
        if char.isspace():
            self.value += char
            return 0
        return -1

    def construct(self) -> None:
        if self.is_mandatory and self.value == "":
            raise ValueError("Invalid space.")


class Partial(ConditionPart):
    def __init__(self) -> None:
        super().__init__()

        self.value = Version(is_in_expression=True)

    def accept(self, char: str) -> int:
        self.value.accept(char)
        return 0

    def construct(self) -> None:
        self.value.construct()

        erase = False
        for i in range(1, 4):
            part = self.value.parts[i]
            if erase:
                part.value = ""
            if part.value in WILDCARD:
                erase = True


class Condition:
    def __init__(self) -> None:
        self.version = Partial()

        self.__parts__: list[ConditionPart] = [self.version]
        self.__current__ = 0

    def accept(self, char: str) -> bool:
        if not char.isspace() or self.__parts__[self.__current__].__can_accept_space__:
            step = self.__parts__[self.__current__].accept(char)
        else:
            self.__parts__[self.__current__].construct()
            step = 1
        self.__current__ += abs(step)

        if self.__current__ >= len(self.__parts__):
            return True

        if step < 0:
            return self.accept(char)

        return False

    def validate(self) -> None:
        self.version.construct()

    def contains(self, version: Version) -> bool:
        pass

    def __str__(self) -> str:
        return ""


class Primitive(Condition):
    def __init__(self, char: str) -> None:
        super().__init__()

        self.comparator = Comparator(char)

        self.__parts__.insert(0, Space())
        self.__parts__.insert(0, self.comparator)

    def contains(self, version: Version) -> bool:
        result = version.compare(self.version.value)

        if result is None:
            return False
        if self.comparator.value == ">":
            return result > 0
        if self.comparator.value == "<":
            return result < 0
        if self.comparator.value == ">=":
            return result >= 0
        if self.comparator.value == "<=":
            return result <= 0
        return result == 0

    def __str__(self) -> str:
        return self.comparator.value + str(self.version.value)


class PartialCondition(Condition):
    def contains(self, version: Version) -> bool:
        return version.compare(self.version.value) == 0

    def __str__(self) -> str:
        return str(self.version.value)


class Tilde(Condition):
    def __init__(self) -> None:
        super().__init__()

        self.__parts__.insert(0, Space())
        self.__bounds__ = [self.version.value]

    def validate(self) -> None:
        super().validate()

        if self.version.value.major.value not in WILDCARD:
            version = Version(is_in_expression=True)
            if self.version.value.minor.value not in WILDCARD:
                version.major.value = self.version.value.major.value
                version.minor.value = str(int(self.version.value.minor.value) + 1)
            elif version.major.value != "":
                version.major.value = str(int(self.version.value.major.value) + 1)
            self.__bounds__.append(version)

    def contains(self, version: Version) -> bool:
        result = version.compare(self.__bounds__[0])
        result = result is not None and result >= 0
        if result and len(self.__bounds__) == 2:
            result = version.compare(self.__bounds__[1], self.__bounds__[0].prerelease.value != "")
            result = result is not None and result < 0
        return result

    def __str__(self) -> str:
        return '~' + str(self.version.value)


class Caret(Tilde):
    def validate(self) -> None:
        super().validate()

        version = Version(is_in_expression=True)

        index = 0
        for i in range(1, 4):
            if self.version.value.parts[i].value not in WILDCARD:
                version.parts[i].value = self.version.value.parts[i].value
                index = i
                if self.version.value.parts[i].value != "0":
                    break
            else:
                break
        if index > 0:
            version.parts[index].value = str(int(version.parts[index].value) + 1)
            self.__bounds__.append(version)

    def __str__(self) -> str:
        return '^' + str(self.version.value)


class Hyphen(Condition):
    def __init__(self, partial: Partial) -> None:
        super().__init__()

        self.__parts__.insert(0, Space(True))
        self.__bounds__ = [partial.value, self.version.value]

    def contains(self, version: Version) -> bool:
        result = version.compare(self.__bounds__[0], True) >= 0 and version.compare(self.__bounds__[1], True) <= 0
        if result and version.prerelease.value != "":
            for bound in self.__bounds__:
                result = bound.prerelease.value != ""
                if result:
                    for i in (1, 4):
                        if version.parts[i].value != bound.parts[i].value:
                            result = False
                        break
                if result:
                    break
        return result

    def __str__(self) -> str:
        return str(self.__bounds__[0]) + ' - ' + str(self.__bounds__[1])


class VersionExpression:
    def __init__(self, expression: str = "") -> None:
        self.ranges = [[]]

        condition = None
        join_begin = False
        for char in expression:
            if join_begin and char != '|':
                raise ValueError("Invalid version expression.")
            if join_begin:
                if condition is not None:
                    condition.validate()
                    self.ranges[-1].append(condition)
                    condition = None
                self.ranges.append([])
                join_begin = False
            elif char == '|':
                join_begin = True
            elif condition is None:
                if char.isspace():
                    continue
                if len(self.ranges[-1]) == 1 and isinstance(self.ranges[-1][0], Hyphen):
                    raise ValueError("Invalid version expression.")

                if char in "<>=":
                    condition = Primitive(char)
                elif char == '~':
                    condition = Tilde()
                elif char == '^':
                    condition = Caret()
                elif char == '-':
                    if len(self.ranges[-1]) != 1 or not isinstance(self.ranges[-1][0], PartialCondition):
                        raise ValueError("Invalid version expression.")
                    condition = Hyphen(self.ranges[-1][0].version)
                    self.ranges[-1].clear()
                else:
                    condition = PartialCondition()
                    condition.accept(char)
            elif condition.accept(char):
                self.ranges[-1].append(condition)
                condition = None
        if condition is not None:
            condition.validate()
            self.ranges[-1].append(condition)

    def contains(self, version: Version) -> bool:
        result = True

        for version_range in self.ranges:
            result = True
            for condition in version_range:
                if not condition.contains(version):
                    result = False
            if result:
                break

        return result

    def __str__(self) -> str:
        value = ""
        for version_range in self.ranges:
            for condition in version_range:
                value += str(condition) + " "
            value += "||"
        return value[:-2] if value != "" else ""
