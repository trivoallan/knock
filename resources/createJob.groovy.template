pipelineJob('$jobPath') {
    definition {
        cpsScm {
            scm {
                git {
                    branch('master')
                    remote {
                        url('$reposUrl')
                        credentials('pic-socle-dosn')
                    }
                }
            }
        }
    }
    parameters{
        booleanParam('ForceImport', false, "Cocher pour forcer l'import de tous les tags (ne prend pas en compte le paramètre \\"Tag à forcer\\").")
        stringParam('TagsToForce', '', 'Spécifier la liste des tags à forcer. Inutile si "Import forcer ?" est coché.\\nFormat : tag1,tag2,tag3')
    }
    triggers{
        cron {
            spec('H 20 * * *')
        }
    }
}
