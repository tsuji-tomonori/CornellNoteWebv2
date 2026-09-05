// 永続要件の一次言語。product固有の要件を追加し、JSONとMarkdownをここから生成する。
module requirements {
  type AcceptanceCriterion = { id: str, given: str, when_: str, expected: str }
  type Verification = { method: str, evidence: str }
  type Traces = {
    design: List[str],
    implementation: List[str],
    tests: List[str],
    standards: List[str],
  }
  type Requirement = {
    id: str,
    revision: int,
    status: str,
    kind: str,
    title: str,
    subject: str,
    actionName: str,
    objectName: str,
    rationale: str,
    sourceRefs: List[str],
    acceptanceCriteria: List[AcceptanceCriterion],
    verification: Verification,
    traces: Traces,
    lastChangedBy: str,
    retirementReason: str,
    supersededBy: str,
    scopeName: str,
    categoryName: str,
  }
  type Catalog = {
    schemaVersion: int,
    catalogRevision: int,
    product: str,
    updatedAt: str,
    requirements: List[Requirement],
  }
  type RequirementOperation = {
    kind: str,
    id: str,
    expectedRevision: int,
    replacement: Requirement,
  }
  type BatchFold = {
    requirements: List[Requirement],
    touchedIds: List[str],
    valid: bool,
  }
  type Lifecycle = {
    catalogRevision: int,
    itemRevision: int,
    itemPresent: bool,
    itemStatus: str,
    traceRevision: int,
    priorCatalogRevision: int,
    priorItemRevision: int,
    priorItemPresent: bool,
    priorItemStatus: str,
    priorTraceRevision: int,
    lastOperation: str,
  }

  pure val requirementsSource: Catalog = {
    schemaVersion: 1,
    catalogRevision: 1,
    product: "replace-with-product-name",
    updatedAt: "1970-01-01",
    requirements: [
      {
        id: "REQ-TEMPLATE-001",
        revision: 1,
        status: "active",
        kind: "constraint",
        title: "要件catalogの初期化",
        subject: "対象repository",
        actionName: "maintain",
        objectName: "product固有の原子的で型付きのQuint要件catalog",
        rationale: "空集合に対するvacuousな検査を避け、導入時から同じcontractを実行する。",
        sourceRefs: ["bootstrap:replace-with-authoritative-source"],
        acceptanceCriteria: [
          { id: "AC-TEMPLATE-001-1", given: "このtemplateを導入した", when_: "product要件を初期化する", expected: "このbootstrap項目を権限あるproduct固有要件へ置き換える" }
        ],
        verification: { method: "Quint test", evidence: "catalogContractTest and lifecycleContractTest" },
        traces: {
          design: [],
          implementation: [],
          tests: [],
          standards: ["QUINT-0.32"],
        },
        lastChangedBy: "bootstrap:init",
        retirementReason: "",
        supersededBy: "",
        scopeName: "project",
        categoryName: "nonfunctional",
      }
    ],
  }

  pure val lifecycleRequirement: Requirement = {
    id: "REQ-LIFECYCLE-MODEL-001",
    revision: 1,
    status: "active",
    kind: "functional",
    title: "lifecycle fixture",
    subject: "requirements lifecycle model",
    actionName: "maintain",
    objectName: "a typed catalog requirement",
    rationale: "A concrete item makes lifecycle refinement non-vacuous.",
    sourceRefs: ["model:requirements-lifecycle"],
    acceptanceCriteria: [
      { id: "AC-LIFECYCLE-MODEL-001-1", given: "a current catalog", when_: "a CAS transition is accepted", expected: "catalog and item revisions advance together" }
    ],
    verification: { method: "Quint model", evidence: "catalog lifecycle transition tests" },
    traces: {
      design: [],
      implementation: [],
      tests: [],
      standards: ["QUINT-0.32"],
    },
    lastChangedBy: "model:add",
    retirementReason: "",
    supersededBy: "",
    scopeName: "project",
    categoryName: "nonfunctional",
  }

  pure val successionR1: Requirement = lifecycleRequirement
    .with("id", "REQ-SUCCESSION-R1")
    .with("acceptanceCriteria", [
      { id: "AC-SUCCESSION-R1", given: "R1 exists", when_: "R1 is superseded", expected: "the chain advances" }
    ])
    .with("status", "retired")
    .with("retirementReason", "superseded by R2")
    .with("supersededBy", "REQ-SUCCESSION-R2")
  pure val successionR2: Requirement = lifecycleRequirement
    .with("id", "REQ-SUCCESSION-R2")
    .with("acceptanceCriteria", [
      { id: "AC-SUCCESSION-R2", given: "R2 exists", when_: "R2 is superseded", expected: "the chain advances" }
    ])
    .with("status", "retired")
    .with("retirementReason", "superseded by R3")
    .with("supersededBy", "REQ-SUCCESSION-R3")
  pure val successionR3: Requirement = lifecycleRequirement
    .with("id", "REQ-SUCCESSION-R3")
    .with("acceptanceCriteria", [
      { id: "AC-SUCCESSION-R3", given: "R3 exists", when_: "the chain terminates", expected: "R3 is active" }
    ])
  pure val successionCycleR2: Requirement = successionR2
    .with("supersededBy", "REQ-SUCCESSION-R1")
  pure val successionRetiredTerminalR2: Requirement = successionR2
    .with("supersededBy", "")
  pure val successionCatalog: Catalog = {
    schemaVersion: 1,
    catalogRevision: 1,
    product: "succession-contract",
    updatedAt: "succession:fixture",
    requirements: [successionR1, successionR2, successionR3],
  }

  pure val batchRequirement1: Requirement = lifecycleRequirement
    .with("id", "REQ-BATCH-1")
    .with("acceptanceCriteria", [
      { id: "AC-BATCH-1", given: "batch source", when_: "item one changes", expected: "revision advances once" }
    ])
  pure val batchRequirement2: Requirement = lifecycleRequirement
    .with("id", "REQ-BATCH-2")
    .with("acceptanceCriteria", [
      { id: "AC-BATCH-2", given: "batch source", when_: "item two changes", expected: "revision advances once" }
    ])
  pure val batchRequirement3: Requirement = lifecycleRequirement
    .with("id", "REQ-BATCH-3")
    .with("acceptanceCriteria", [
      { id: "AC-BATCH-3", given: "batch source", when_: "item three changes", expected: "revision advances once" }
    ])
  pure val batchBefore: Catalog = {
    schemaVersion: 1,
    catalogRevision: 5,
    product: "batch-contract",
    updatedAt: "batch:before",
    requirements: [batchRequirement1, batchRequirement2, batchRequirement3],
  }
  pure val batchAfterTwo: Catalog = batchBefore
    .with("catalogRevision", 6)
    .with("updatedAt", "batch:two")
    .with("requirements", [
      batchRequirement1
        .with("revision", 2)
        .with("title", "batch item one updated")
        .with("lastChangedBy", "batch:change"),
      batchRequirement2
        .with("revision", 2)
        .with("traces", batchRequirement2.traces.with("tests", ["tests/batch-two.py"]))
        .with("lastChangedBy", "batch:change"),
      batchRequirement3,
    ])
  pure val batchAfterThree: Catalog = batchBefore
    .with("catalogRevision", 6)
    .with("updatedAt", "batch:three")
    .with("requirements", [
      batchAfterTwo.requirements.nth(0),
      batchAfterTwo.requirements.nth(1),
      batchRequirement3
        .with("revision", 2)
        .with("status", "retired")
        .with("retirementReason", "batch retirement")
        .with("lastChangedBy", "batch:change"),
    ])
  pure val batchStaleAfter: Catalog = batchAfterTwo.with("requirements", [
    batchRequirement1,
    batchAfterTwo.requirements.nth(1),
    batchRequirement3,
  ])
  pure val batchPartialAfterStale: Catalog = batchBefore
    .with("catalogRevision", 6)
    .with("updatedAt", "batch:stale-after-valid")
    .with("requirements", [
      batchAfterTwo.requirements.nth(0),
      batchRequirement2,
      batchRequirement3,
    ])
  pure val batchInvalidAfter: Catalog = batchAfterTwo.with("requirements", [
    batchAfterTwo.requirements.nth(0).with("title", ""),
    batchAfterTwo.requirements.nth(1),
    batchRequirement3,
  ])
  pure val batchUpdateOperation: RequirementOperation = {
    kind: "update",
    id: "REQ-BATCH-1",
    expectedRevision: 1,
    replacement: batchAfterTwo.requirements.nth(0),
  }
  pure val batchTraceOperation: RequirementOperation = {
    kind: "trace",
    id: "REQ-BATCH-2",
    expectedRevision: 1,
    replacement: batchAfterTwo.requirements.nth(1),
  }
  pure val batchRetireOperation: RequirementOperation = {
    kind: "retire",
    id: "REQ-BATCH-3",
    expectedRevision: 1,
    replacement: batchAfterThree.requirements.nth(2),
  }
  pure val batchStaleOperation: RequirementOperation = batchUpdateOperation
    .with("expectedRevision", 0)
  pure val batchStaleTraceOperation: RequirementOperation = batchTraceOperation
    .with("expectedRevision", 0)
  pure val batchInvalidOperation: RequirementOperation = batchUpdateOperation
    .with("replacement", batchInvalidAfter.requirements.nth(0))
  pure val batchResurrectionOperation: RequirementOperation = {
    kind: "update",
    id: "REQ-BATCH-3",
    expectedRevision: 2,
    replacement: batchAfterThree.requirements.nth(2)
      .with("revision", 3)
      .with("status", "active")
      .with("retirementReason", "")
      .with("lastChangedBy", "batch:change"),
  }
  pure val batchResurrectedAfter: Catalog = batchAfterThree
    .with("catalogRevision", 7)
    .with("updatedAt", "batch:resurrection")
    .with("requirements", batchAfterThree.requirements.replaceAt(
      2,
      batchResurrectionOperation.replacement
    ))

  var catalog: Catalog
  var lifecycle: Lifecycle

  action init = all {
    catalog' = requirementsSource,
    lifecycle' = {
      catalogRevision: requirementsSource.catalogRevision,
      itemRevision: 0,
      itemPresent: false,
      itemStatus: "missing",
      traceRevision: 0,
      priorCatalogRevision: requirementsSource.catalogRevision,
      priorItemRevision: 0,
      priorItemPresent: false,
      priorItemStatus: "missing",
      priorTraceRevision: 0,
      lastOperation: "init",
    },
  }

  action addRequirementAt(expectedCatalogRevision: int): bool = all {
    expectedCatalogRevision == catalog.catalogRevision,
    lifecycle.catalogRevision == expectedCatalogRevision,
    not(lifecycle.itemPresent),
    catalog.requirements.indices().forall(i =>
      catalog.requirements.nth(i).id != lifecycleRequirement.id
    ),
    catalog' = catalog
      .with("catalogRevision", catalog.catalogRevision + 1)
      .with("requirements", catalog.requirements.append(lifecycleRequirement)),
    lifecycle' = {
      catalogRevision: lifecycle.catalogRevision + 1,
      itemRevision: 1,
      itemPresent: true,
      itemStatus: "active",
      traceRevision: 0,
      priorCatalogRevision: lifecycle.catalogRevision,
      priorItemRevision: lifecycle.itemRevision,
      priorItemPresent: lifecycle.itemPresent,
      priorItemStatus: lifecycle.itemStatus,
      priorTraceRevision: lifecycle.traceRevision,
      lastOperation: "add",
    },
  }

  action addRequirement = addRequirementAt(lifecycle.catalogRevision)

  def updateRequirementIsAllowed(expectedCatalogRevision: int, expectedItemRevision: int): bool =
    all {
      lifecycle.itemPresent,
      lifecycle.itemStatus == "active",
      expectedCatalogRevision == catalog.catalogRevision,
      expectedCatalogRevision == lifecycle.catalogRevision,
      expectedItemRevision == lifecycle.itemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).id == lifecycleRequirement.id,
      catalog.requirements.nth(catalog.requirements.length() - 1).revision == expectedItemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).status == "active",
      catalog.requirements.nth(catalog.requirements.length() - 1).title != "lifecycle fixture updated",
    }

  action updateRequirementAt(expectedCatalogRevision: int, expectedItemRevision: int): bool = all {
    updateRequirementIsAllowed(expectedCatalogRevision, expectedItemRevision),
    catalog' = catalog
      .with("catalogRevision", catalog.catalogRevision + 1)
      .with(
        "requirements",
        catalog.requirements.replaceAt(
          catalog.requirements.length() - 1,
          catalog.requirements.nth(catalog.requirements.length() - 1)
            .with("revision", expectedItemRevision + 1)
            .with("title", "lifecycle fixture updated")
            .with("lastChangedBy", "model:update")
        )
      ),
    lifecycle' = {
      catalogRevision: lifecycle.catalogRevision + 1,
      itemRevision: lifecycle.itemRevision + 1,
      itemPresent: true,
      itemStatus: "active",
      traceRevision: lifecycle.traceRevision,
      priorCatalogRevision: lifecycle.catalogRevision,
      priorItemRevision: lifecycle.itemRevision,
      priorItemPresent: lifecycle.itemPresent,
      priorItemStatus: lifecycle.itemStatus,
      priorTraceRevision: lifecycle.traceRevision,
      lastOperation: "update",
    },
  }

  action updateRequirement = updateRequirementAt(lifecycle.catalogRevision, lifecycle.itemRevision)

  def traceUpdateIsAllowed(expectedCatalogRevision: int, expectedItemRevision: int): bool =
    all {
      lifecycle.itemPresent,
      lifecycle.itemStatus == "active",
      lifecycle.traceRevision == 0,
      expectedCatalogRevision == catalog.catalogRevision,
      expectedCatalogRevision == lifecycle.catalogRevision,
      expectedItemRevision == lifecycle.itemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).id == lifecycleRequirement.id,
      catalog.requirements.nth(catalog.requirements.length() - 1).revision == expectedItemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).status == "active",
    }

  action updateRequirementTraceAt(expectedCatalogRevision: int, expectedItemRevision: int): bool = all {
    traceUpdateIsAllowed(expectedCatalogRevision, expectedItemRevision),
    catalog' = catalog
      .with("catalogRevision", catalog.catalogRevision + 1)
      .with(
        "requirements",
        catalog.requirements.replaceAt(
          catalog.requirements.length() - 1,
          catalog.requirements.nth(catalog.requirements.length() - 1)
            .with("revision", expectedItemRevision + 1)
            .with(
              "traces",
              catalog.requirements.nth(catalog.requirements.length() - 1).traces.with(
                "tests",
                catalog.requirements.nth(catalog.requirements.length() - 1).traces.tests
                  .append("tests/model-trace-update.py")
              )
            )
            .with("lastChangedBy", "model:trace-update")
        )
      ),
    lifecycle' = {
      catalogRevision: lifecycle.catalogRevision + 1,
      itemRevision: lifecycle.itemRevision + 1,
      itemPresent: true,
      itemStatus: "active",
      traceRevision: lifecycle.traceRevision + 1,
      priorCatalogRevision: lifecycle.catalogRevision,
      priorItemRevision: lifecycle.itemRevision,
      priorItemPresent: lifecycle.itemPresent,
      priorItemStatus: lifecycle.itemStatus,
      priorTraceRevision: lifecycle.traceRevision,
      lastOperation: "trace-update",
    },
  }

  action updateRequirementTrace =
    updateRequirementTraceAt(lifecycle.catalogRevision, lifecycle.itemRevision)

  def retirementIsAllowed(expectedCatalogRevision: int, expectedItemRevision: int): bool =
    all {
      lifecycle.itemPresent,
      lifecycle.itemStatus == "active",
      expectedCatalogRevision == catalog.catalogRevision,
      expectedCatalogRevision == lifecycle.catalogRevision,
      expectedItemRevision == lifecycle.itemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).id == lifecycleRequirement.id,
      catalog.requirements.nth(catalog.requirements.length() - 1).revision == expectedItemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).status == "active",
    }

  action retireRequirementAt(expectedCatalogRevision: int, expectedItemRevision: int): bool = all {
    retirementIsAllowed(expectedCatalogRevision, expectedItemRevision),
    catalog' = catalog
      .with("catalogRevision", catalog.catalogRevision + 1)
      .with(
        "requirements",
        catalog.requirements.replaceAt(
          catalog.requirements.length() - 1,
          catalog.requirements.nth(catalog.requirements.length() - 1)
            .with("revision", expectedItemRevision + 1)
            .with("status", "retired")
            .with("retirementReason", "model retirement")
            .with("lastChangedBy", "model:retire")
        )
      ),
    lifecycle' = {
      catalogRevision: lifecycle.catalogRevision + 1,
      itemRevision: lifecycle.itemRevision + 1,
      itemPresent: true,
      itemStatus: "retired",
      traceRevision: lifecycle.traceRevision,
      priorCatalogRevision: lifecycle.catalogRevision,
      priorItemRevision: lifecycle.itemRevision,
      priorItemPresent: lifecycle.itemPresent,
      priorItemStatus: lifecycle.itemStatus,
      priorTraceRevision: lifecycle.traceRevision,
      lastOperation: "retire",
    },
  }

  action retireRequirement = retireRequirementAt(lifecycle.catalogRevision, lifecycle.itemRevision)

  action lifecycleStutter = all {
    catalog' = catalog,
    lifecycle' = {
      catalogRevision: lifecycle.catalogRevision,
      itemRevision: lifecycle.itemRevision,
      itemPresent: lifecycle.itemPresent,
      itemStatus: lifecycle.itemStatus,
      traceRevision: lifecycle.traceRevision,
      priorCatalogRevision: lifecycle.catalogRevision,
      priorItemRevision: lifecycle.itemRevision,
      priorItemPresent: lifecycle.itemPresent,
      priorItemStatus: lifecycle.itemStatus,
      priorTraceRevision: lifecycle.traceRevision,
      lastOperation: "none",
    },
  }

  action counterOnlyMutation = all {
    catalog' = catalog,
    lifecycle' = lifecycle.with("catalogRevision", lifecycle.catalogRevision + 1),
  }

  action step = any {
    addRequirement,
    updateRequirement,
    updateRequirementTrace,
    retireRequirement,
    lifecycleStutter,
  }

  pure val allowedStatuses = Set("active", "retired")
  pure val allowedKinds = Set("functional", "quality", "constraint", "interface", "data", "operational")
  pure val allowedScopes = Set("product", "project")
  pure val allowedCategories = Set("functional", "nonfunctional")
  pure val allowedActions = Set(
    "constrain", "derive", "detect", "discover", "enable", "enforce", "estimate",
    "expand", "formalize", "generate", "maintain", "measure", "parse", "preserve",
    "provide", "route", "select", "separate", "stage", "stop", "structure", "validate", "verify"
  )

  pure def stringsAreUnique(values: List[str]): bool = values.indices().forall(i =>
    values.indices().forall(j => i == j or values.nth(i) != values.nth(j))
  )

  pure def stringsAreNonempty(values: List[str]): bool =
    values.indices().forall(i => values.nth(i) != "")

  pure def requirementIdsAreUniqueIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i =>
      requirements.indices().forall(j =>
        i == j or requirements.nth(i).id != requirements.nth(j).id
      )
    )

  val requirementIdsAreUnique = requirementIdsAreUniqueIn(catalog.requirements)

  // 構造的完全性は機械検査する。1 IDが意味的に1義務だけを表すかは、
  // 自然言語を解釈できる権限あるhuman semantic reviewの責務である。
  pure def requirementsAreStructurallyCompleteIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i => all {
      requirements.nth(i).id != "",
      requirements.nth(i).revision >= 1,
      requirements.nth(i).title != "",
      requirements.nth(i).subject != "",
      requirements.nth(i).actionName != "",
      requirements.nth(i).objectName != "",
      requirements.nth(i).rationale != "",
      requirements.nth(i).lastChangedBy != "",
      requirements.nth(i).sourceRefs.length() > 0,
      stringsAreNonempty(requirements.nth(i).sourceRefs),
      stringsAreUnique(requirements.nth(i).sourceRefs),
      requirements.nth(i).acceptanceCriteria.length() > 0,
      requirements.nth(i).verification.method != "",
      requirements.nth(i).verification.evidence != "",
    })

  val requirementsAreStructurallyComplete =
    requirementsAreStructurallyCompleteIn(catalog.requirements)

  pure def requirementsAreTypedIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i => all {
      allowedStatuses.contains(requirements.nth(i).status),
      allowedKinds.contains(requirements.nth(i).kind),
      allowedActions.contains(requirements.nth(i).actionName),
      (requirements.nth(i).scopeName == "").or(allowedScopes.contains(requirements.nth(i).scopeName)),
      (requirements.nth(i).categoryName == "").or(allowedCategories.contains(requirements.nth(i).categoryName)),
    })

  val requirementsAreTyped = requirementsAreTypedIn(catalog.requirements)

  pure def acceptanceCriteriaAreCompleteIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i =>
      requirements.nth(i).acceptanceCriteria.indices().forall(j => all {
        requirements.nth(i).acceptanceCriteria.nth(j).id != "",
        requirements.nth(i).acceptanceCriteria.nth(j).given != "",
        requirements.nth(i).acceptanceCriteria.nth(j).when_ != "",
        requirements.nth(i).acceptanceCriteria.nth(j).expected != "",
      })
    )

  val acceptanceCriteriaAreComplete =
    acceptanceCriteriaAreCompleteIn(catalog.requirements)

  pure def acceptanceCriterionIdsAreUniqueIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i =>
      requirements.indices().forall(j =>
        requirements.nth(i).acceptanceCriteria.indices().forall(x =>
          requirements.nth(j).acceptanceCriteria.indices().forall(y =>
          (i == j and x == y) or
            requirements.nth(i).acceptanceCriteria.nth(x).id !=
              requirements.nth(j).acceptanceCriteria.nth(y).id
          )
        )
      )
    )

  val acceptanceCriterionIdsAreUnique =
    acceptanceCriterionIdsAreUniqueIn(catalog.requirements)

  pure def traceLinksAreUniqueIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i => all {
      stringsAreNonempty(requirements.nth(i).traces.design),
      stringsAreNonempty(requirements.nth(i).traces.implementation),
      stringsAreNonempty(requirements.nth(i).traces.tests),
      stringsAreNonempty(requirements.nth(i).traces.standards),
      stringsAreUnique(requirements.nth(i).traces.design),
      stringsAreUnique(requirements.nth(i).traces.implementation),
      stringsAreUnique(requirements.nth(i).traces.tests),
      stringsAreUnique(requirements.nth(i).traces.standards),
    })

  val traceLinksAreUnique = traceLinksAreUniqueIn(catalog.requirements)

  pure def classificationIsPairedIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i =>
      (requirements.nth(i).scopeName == "") iff
      (requirements.nth(i).categoryName == "")
    )

  val classificationIsPaired = classificationIsPairedIn(catalog.requirements)

  pure def retirementFieldsAreConsistentIn(requirements: List[Requirement]): bool =
    requirements.indices().forall(i => all {
    (requirements.nth(i).status == "active").implies(all {
      requirements.nth(i).retirementReason == "",
      requirements.nth(i).supersededBy == "",
    }),
    (requirements.nth(i).status == "retired").implies(
      requirements.nth(i).retirementReason != ""
    ),
    (requirements.nth(i).supersededBy != "").implies(all {
      requirements.nth(i).status == "retired",
      requirements.nth(i).supersededBy != requirements.nth(i).id,
    }),
  })

  val retirementFieldsAreConsistent =
    retirementFieldsAreConsistentIn(catalog.requirements)

  pure def supersessionChainsAreValid(requirements: List[Requirement]): bool =
    requirements.indices().forall(i =>
      (requirements.nth(i).supersededBy != "").implies(
        requirements.indices().exists(j => all {
          j > i,
          requirements.nth(j).id == requirements.nth(i).supersededBy,
          requirements.nth(j).id != requirements.nth(i).id,
          (requirements.nth(j).status == "active").or(all {
            requirements.nth(j).status == "retired",
            requirements.nth(j).supersededBy != "",
          }),
        })
      )
    )

  pure def catalogHeaderIsValid(source: Catalog): bool = all {
    source.schemaVersion == 1,
    source.catalogRevision >= 1,
    source.product != "",
    source.updatedAt != "",
    source.requirements.length() > 0,
  }

  // Pure catalog component of catalogWellFormed. Lifecycle witness refinement
  // remains a state invariant below and is intentionally not fabricated for a
  // caller-supplied batch result.
  pure def catalogDataWellFormed(source: Catalog): bool = all {
    catalogHeaderIsValid(source),
    requirementIdsAreUniqueIn(source.requirements),
    requirementsAreStructurallyCompleteIn(source.requirements),
    requirementsAreTypedIn(source.requirements),
    acceptanceCriteriaAreCompleteIn(source.requirements),
    acceptanceCriterionIdsAreUniqueIn(source.requirements),
    traceLinksAreUniqueIn(source.requirements),
    classificationIsPairedIn(source.requirements),
    retirementFieldsAreConsistentIn(source.requirements),
    supersessionChainsAreValid(source.requirements),
  }

  pure def stringsContain(values: List[str], value: str): bool =
    values.indices().exists(i => values.nth(i) == value)

  pure def requirementExists(requirements: List[Requirement], id: str): bool =
    requirements.indices().exists(i => requirements.nth(i).id == id)

  pure def requirementById(requirements: List[Requirement], id: str): Requirement =
    requirements.select(requirement => requirement.id == id).head()

  pure def replaceRequirement(
    requirements: List[Requirement],
    id: str,
    replacement: Requirement,
  ): List[Requirement] =
    range(0, requirements.length()).foldl(requirements, (result, index) =>
      if (result.nth(index).id == id)
        result.replaceAt(index, replacement)
      else
        result
    )

  pure def updateReplacementIsValid(
    current: Requirement,
    replacement: Requirement,
    changeId: str,
  ): bool = all {
    current.status == "active",
    replacement == current
      .with("revision", current.revision + 1)
      .with("kind", replacement.kind)
      .with("title", replacement.title)
      .with("subject", replacement.subject)
      .with("actionName", replacement.actionName)
      .with("objectName", replacement.objectName)
      .with("rationale", replacement.rationale)
      .with("sourceRefs", replacement.sourceRefs)
      .with("acceptanceCriteria", replacement.acceptanceCriteria)
      .with("verification", replacement.verification)
      .with("scopeName", replacement.scopeName)
      .with("categoryName", replacement.categoryName)
      .with("lastChangedBy", changeId),
    replacement
      .with("revision", current.revision)
      .with("lastChangedBy", current.lastChangedBy) != current,
  }

  pure def traceReplacementIsValid(
    current: Requirement,
    replacement: Requirement,
    changeId: str,
  ): bool = all {
    current.status == "active",
    replacement.traces != current.traces,
    replacement == current
      .with("revision", current.revision + 1)
      .with("traces", replacement.traces)
      .with("lastChangedBy", changeId),
  }

  pure def retirementReplacementIsValid(
    current: Requirement,
    replacement: Requirement,
    changeId: str,
  ): bool = all {
    current.status == "active",
    replacement.retirementReason != "",
    replacement == current
      .with("revision", current.revision + 1)
      .with("status", "retired")
      .with("retirementReason", replacement.retirementReason)
      .with("supersededBy", replacement.supersededBy)
      .with("lastChangedBy", changeId),
  }

  pure def batchOperationIsAllowed(
    accumulator: BatchFold,
    operation: RequirementOperation,
    changeId: str,
  ): bool =
    if (not(accumulator.valid)) false
    else if (stringsContain(accumulator.touchedIds, operation.id)) false
    else if (operation.kind == "add") all {
      not(requirementExists(accumulator.requirements, operation.id)),
      operation.expectedRevision == 0,
      operation.id == operation.replacement.id,
      operation.replacement.revision == 1,
      operation.replacement.status == "active",
      operation.replacement.retirementReason == "",
      operation.replacement.supersededBy == "",
      operation.replacement.lastChangedBy == changeId,
    }
    else if (not(requirementExists(accumulator.requirements, operation.id))) false
    else if (
      operation.expectedRevision !=
        requirementById(accumulator.requirements, operation.id).revision
    ) false
    else if (operation.kind == "update") updateReplacementIsValid(
      requirementById(accumulator.requirements, operation.id),
      operation.replacement,
      changeId
    )
    else if (operation.kind == "trace") traceReplacementIsValid(
      requirementById(accumulator.requirements, operation.id),
      operation.replacement,
      changeId
    )
    else if (operation.kind == "retire") retirementReplacementIsValid(
      requirementById(accumulator.requirements, operation.id),
      operation.replacement,
      changeId
    )
    else false

  pure def applyBatchOperation(
    accumulator: BatchFold,
    operation: RequirementOperation,
    changeId: str,
  ): BatchFold =
    if (batchOperationIsAllowed(accumulator, operation, changeId)) {
      requirements:
        if (operation.kind == "add")
          accumulator.requirements.append(operation.replacement)
        else
          replaceRequirement(accumulator.requirements, operation.id, operation.replacement),
      touchedIds: accumulator.touchedIds.append(operation.id),
      valid: true,
    } else accumulator.with("valid", false)

  pure def initialBatchFold(before: Catalog): BatchFold = {
    requirements: before.requirements,
    touchedIds: [],
    valid: true,
  }

  pure def foldBatchOperations(
    before: Catalog,
    operations: List[RequirementOperation],
    changeId: str,
  ): BatchFold = operations.foldl(
    initialBatchFold(before),
    (accumulator, operation) => applyBatchOperation(accumulator, operation, changeId)
  )

  pure def batchCandidate(
    before: Catalog,
    operations: List[RequirementOperation],
    changedAt: str,
    changeId: str,
  ): Catalog = before
    .with("catalogRevision", before.catalogRevision + 1)
    .with("updatedAt", changedAt)
    .with("requirements", foldBatchOperations(before, operations, changeId).requirements)

  pure def batchWouldBeAccepted(
    before: Catalog,
    expectedCatalogRevision: int,
    operations: List[RequirementOperation],
    changedAt: str,
    changeId: str,
  ): bool = all {
    expectedCatalogRevision == before.catalogRevision,
    operations.length() > 0,
    changedAt != "",
    changeId != "",
    foldBatchOperations(before, operations, changeId).valid,
    catalogDataWellFormed(batchCandidate(before, operations, changedAt, changeId)),
  }

  // This relation models the same arbitrary-length operation fold and CAS
  // boundary as specflow.apply_change. No operation may resurrect a retired
  // item, and any stale or invalid member makes the entire batch stutter.
  pure def atomicBatchTransitionIsValid(
    before: Catalog,
    after: Catalog,
    expectedCatalogRevision: int,
    operations: List[RequirementOperation],
    changedAt: str,
    changeId: str,
    outcome: str,
  ): bool = all {
    Set("accepted", "rejected").contains(outcome),
    catalogDataWellFormed(before),
    (outcome == "accepted") iff batchWouldBeAccepted(
      before, expectedCatalogRevision, operations, changedAt, changeId
    ),
    (outcome == "accepted").implies(
      after == batchCandidate(before, operations, changedAt, changeId)
    ),
    (outcome == "rejected").implies(after == before),
  }

  val lifecycleRevisionTransitionIsSound = all {
    Set("init", "add", "update", "trace-update", "retire", "none").contains(lifecycle.lastOperation),
    (lifecycle.lastOperation == "init").implies(all {
      lifecycle.catalogRevision == requirementsSource.catalogRevision,
      lifecycle.itemRevision == 0,
      not(lifecycle.itemPresent),
    }),
    (lifecycle.lastOperation == "add").implies(all {
      not(lifecycle.priorItemPresent),
      lifecycle.itemPresent,
      lifecycle.itemStatus == "active",
      lifecycle.catalogRevision == lifecycle.priorCatalogRevision + 1,
      lifecycle.itemRevision == 1,
    }),
    (lifecycle.lastOperation == "update").implies(all {
      lifecycle.priorItemPresent,
      lifecycle.priorItemStatus == "active",
      lifecycle.itemStatus == "active",
      lifecycle.catalogRevision == lifecycle.priorCatalogRevision + 1,
      lifecycle.itemRevision == lifecycle.priorItemRevision + 1,
      lifecycle.traceRevision == lifecycle.priorTraceRevision,
    }),
    (lifecycle.lastOperation == "trace-update").implies(all {
      lifecycle.priorItemPresent,
      lifecycle.priorItemStatus == "active",
      lifecycle.itemStatus == "active",
      lifecycle.catalogRevision == lifecycle.priorCatalogRevision + 1,
      lifecycle.itemRevision == lifecycle.priorItemRevision + 1,
      lifecycle.traceRevision == lifecycle.priorTraceRevision + 1,
    }),
    (lifecycle.lastOperation == "retire").implies(all {
      lifecycle.priorItemPresent,
      lifecycle.priorItemStatus == "active",
      lifecycle.itemPresent,
      lifecycle.itemStatus == "retired",
      lifecycle.catalogRevision == lifecycle.priorCatalogRevision + 1,
      lifecycle.itemRevision == lifecycle.priorItemRevision + 1,
      lifecycle.traceRevision == lifecycle.priorTraceRevision,
    }),
    (lifecycle.lastOperation == "none").implies(all {
      lifecycle.catalogRevision == lifecycle.priorCatalogRevision,
      lifecycle.itemRevision == lifecycle.priorItemRevision,
      lifecycle.itemPresent == lifecycle.priorItemPresent,
      lifecycle.itemStatus == lifecycle.priorItemStatus,
      lifecycle.traceRevision == lifecycle.priorTraceRevision,
    }),
  }

  val lifecycleRefinesCatalog = all {
    lifecycle.catalogRevision == catalog.catalogRevision,
    lifecycle.itemPresent iff
      catalog.requirements.indices().exists(i =>
        catalog.requirements.nth(i).id == lifecycleRequirement.id
      ),
    lifecycle.itemPresent.implies(all {
      catalog.requirements.nth(catalog.requirements.length() - 1).id == lifecycleRequirement.id,
      catalog.requirements.nth(catalog.requirements.length() - 1).revision == lifecycle.itemRevision,
      catalog.requirements.nth(catalog.requirements.length() - 1).status == lifecycle.itemStatus,
      (lifecycle.traceRevision == 0).implies(
        catalog.requirements.nth(catalog.requirements.length() - 1).traces.tests ==
          lifecycleRequirement.traces.tests
      ),
      (lifecycle.traceRevision == 1).implies(
        catalog.requirements.nth(catalog.requirements.length() - 1).traces.tests ==
          lifecycleRequirement.traces.tests.append("tests/model-trace-update.py")
      ),
    }),
  }

  val catalogWellFormed = all {
    catalogDataWellFormed(catalog),
    lifecycleRevisionTransitionIsSound,
    lifecycleRefinesCatalog,
  }

  run catalogContractTest = {
    init.then(all {
      assert(catalogWellFormed),
      catalog' = catalog,
      lifecycle' = lifecycle,
    })
  }

  run catalogAndSupersessionMutationRejectionTest = {
    init.then(all {
      assert(not(catalogHeaderIsValid(catalog.with("requirements", [])))),
      assert(catalogDataWellFormed(successionCatalog)),
      assert(supersessionChainsAreValid([successionR1, successionR2, successionR3])),
      assert(not(catalogDataWellFormed(successionCatalog.with("requirements", [successionR1])))),
      assert(not(catalogDataWellFormed(successionCatalog.with("requirements", [successionR1, successionRetiredTerminalR2])))),
      assert(not(catalogDataWellFormed(successionCatalog.with("requirements", [successionR1, successionCycleR2])))),
      assert(not(supersessionChainsAreValid([successionR1]))),
      assert(not(supersessionChainsAreValid([successionR1, successionRetiredTerminalR2]))),
      assert(not(supersessionChainsAreValid([successionR1, successionCycleR2]))),
      catalog' = catalog,
      lifecycle' = lifecycle,
    })
  }

  run atomicBatchTransitionContractTest = {
    init.then(all {
      assert(atomicBatchTransitionIsValid(batchBefore, batchAfterTwo, 5, [batchUpdateOperation, batchTraceOperation], "batch:two", "batch:change", "accepted")),
      assert(atomicBatchTransitionIsValid(batchBefore, batchAfterThree, 5, [batchUpdateOperation, batchTraceOperation, batchRetireOperation], "batch:three", "batch:change", "accepted")),
      assert(atomicBatchTransitionIsValid(batchBefore, batchBefore, 4, [batchUpdateOperation], "batch:stale-catalog", "batch:change", "rejected")),
      assert(atomicBatchTransitionIsValid(batchBefore, batchBefore, 5, [batchStaleOperation], "batch:stale-item", "batch:change", "rejected")),
      assert(atomicBatchTransitionIsValid(batchBefore, batchBefore, 5, [batchUpdateOperation, batchStaleTraceOperation], "batch:stale-after-valid", "batch:change", "rejected")),
      assert(not(atomicBatchTransitionIsValid(batchBefore, batchPartialAfterStale, 5, [batchUpdateOperation, batchStaleTraceOperation], "batch:stale-after-valid", "batch:change", "accepted"))),
      assert(atomicBatchTransitionIsValid(batchBefore, batchBefore, 5, [batchUpdateOperation, batchUpdateOperation], "batch:duplicate", "batch:change", "rejected")),
      assert(atomicBatchTransitionIsValid(batchBefore, batchBefore, 5, [batchInvalidOperation], "batch:invalid", "batch:change", "rejected")),
      assert(not(atomicBatchTransitionIsValid(batchBefore, batchInvalidAfter, 5, [batchInvalidOperation], "batch:invalid", "batch:change", "accepted"))),
      assert(catalogDataWellFormed(batchResurrectedAfter)),
      assert(atomicBatchTransitionIsValid(batchAfterThree, batchAfterThree, 6, [batchResurrectionOperation], "batch:resurrection", "batch:change", "rejected")),
      assert(not(atomicBatchTransitionIsValid(batchAfterThree, batchResurrectedAfter, 6, [batchResurrectionOperation], "batch:resurrection", "batch:change", "accepted"))),
      catalog' = catalog,
      lifecycle' = lifecycle,
    })
  }

  run lifecycleContractTest = {
    init
      .then(addRequirement)
      .then(updateRequirement)
      .then(updateRequirementTrace)
      .then(retireRequirement)
      .then(all {
        assert(catalogWellFormed),
        assert(lifecycleRefinesCatalog),
        assert(not(updateRequirementIsAllowed(catalog.catalogRevision, lifecycle.itemRevision))),
        assert(not(traceUpdateIsAllowed(catalog.catalogRevision, lifecycle.itemRevision))),
        catalog' = catalog,
        lifecycle' = lifecycle,
      })
  }

  run lifecycleCasRejectionTest = {
    init
      .then(addRequirement)
      .then(all {
        assert(not(updateRequirementIsAllowed(catalog.catalogRevision - 1, lifecycle.itemRevision))),
        assert(not(updateRequirementIsAllowed(catalog.catalogRevision, lifecycle.itemRevision - 1))),
        catalog' = catalog,
        lifecycle' = lifecycle,
      })
  }


  run refinementRejectsCounterOnlyMutationTest = {
    init
      .then(counterOnlyMutation)
      .then(all {
        assert(not(lifecycleRefinesCatalog)),
        catalog' = catalog,
        lifecycle' = lifecycle,
      })
  }
}
